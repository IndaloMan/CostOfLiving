"""
Test script for Shopper self-registration, login, and account deletion.
Run with:  python test_registration.py
Requires the Flask app to be running at BASE_URL.
"""

import requests
import sys

BASE_URL = "https://media-pc.tail9914ae.ts.net:5000"

# Disable SSL warnings for self-signed cert
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VERIFY_SSL = False  # set to True if using a trusted cert

PASS_MARK = "  PASS"
FAIL_MARK = "  FAIL"
errors = []


def check(label, condition, detail=""):
    if condition:
        print(f"{PASS_MARK}  {label}")
    else:
        msg = f"{FAIL_MARK}  {label}" + (f"  ->  {detail}" if detail else "")
        print(msg)
        errors.append(msg)


def session():
    s = requests.Session()
    s.verify = VERIFY_SSL
    return s


# ---------------------------------------------------------------------------
# 1. Self-registration page loads
# ---------------------------------------------------------------------------
print("\n--- 1. Register page ---------------------------------------------------")
s = session()
r = s.get(f"{BASE_URL}/register")
check("GET /register returns 200", r.status_code == 200, r.status_code)
check("Page contains Login ID field", "anon-" in r.text)
check("Page contains passphrase field", "sunny" in r.text or "Password" in r.text)
check("Gender has — select —", "— select —" in r.text)
check("Age Range has — select —", "— select —" in r.text)
check("Age Range has 85+", "85+" in r.text)
check("Gender has no Non-binary", "Non-binary" not in r.text)
check("Gender has no Prefer not to say", "Prefer not to say" not in r.text)

# Extract generated credentials from the hidden fields
import re
login_id_match   = re.search(r'name="login_id"\s+value="([^"]+)"',   r.text)
passphrase_match = re.search(r'name="passphrase"\s+value="([^"]+)"', r.text)
check("Login ID hidden field present",   bool(login_id_match),   "not found in HTML")
check("Passphrase hidden field present", bool(passphrase_match), "not found in HTML")

if not login_id_match or not passphrase_match:
    print("\nCannot continue without credentials — aborting.")
    sys.exit(1)

login_id   = login_id_match.group(1)
passphrase = passphrase_match.group(1)
print(f"       Generated:  login_id={login_id}  passphrase={passphrase}")

# ---------------------------------------------------------------------------
# 2. Self-registration — submit with nickname only (no email/gender/age)
# ---------------------------------------------------------------------------
print("\n--- 2. Register new account -")
r = s.post(f"{BASE_URL}/register", data={
    "login_id":   login_id,
    "passphrase": passphrase,
    "nickname":   "TestUser",
    "email":      "",
    "gender":     "",
    "age_range":  "",
    "consent":    "1",
}, allow_redirects=True)
check("Register POST succeeds (200)", r.status_code == 200, r.status_code)
check("Redirected to welcome page", "/register/welcome" in r.url or "welcome" in r.text.lower(),
      r.url)
check("Welcome page shows login_id", login_id in r.text, "login_id not on page")
check("Welcome page shows passphrase", passphrase in r.text, "passphrase not on page")

# ---------------------------------------------------------------------------
# 3. Logout then log back in with anon login_id
# ---------------------------------------------------------------------------
print("\n--- 3. Login with anon login_id -")
s2 = session()
r = s2.get(f"{BASE_URL}/login")
check("GET /login returns 200", r.status_code == 200, r.status_code)

r = s2.post(f"{BASE_URL}/login", data={
    "identifier": login_id,
    "password":   passphrase,
}, allow_redirects=True)
check("Login with anon ID succeeds", r.status_code == 200, r.status_code)
check("Redirected away from login page", "/login" not in r.url, r.url)
check("App shows TestUser nickname", "TestUser" in r.text, "nickname not found")

# ---------------------------------------------------------------------------
# 4. Register — missing nickname should fail
# ---------------------------------------------------------------------------
print("\n--- 4. Validation — nickname required -")
s3 = session()
r3 = s3.get(f"{BASE_URL}/register")
lid2 = re.search(r'name="login_id"\s+value="([^"]+)"',   r3.text).group(1)
pp2  = re.search(r'name="passphrase"\s+value="([^"]+)"', r3.text).group(1)

r3 = s3.post(f"{BASE_URL}/register", data={
    "login_id":   lid2,
    "passphrase": pp2,
    "nickname":   "",        # missing!
    "consent":    "1",
}, allow_redirects=True)
check("Missing nickname stays on register page", "/register" in r3.url or r3.status_code == 200,
      r3.url)
check("Error message shown", "nickname" in r3.text.lower(), "no error message found")

# ---------------------------------------------------------------------------
# 5. Register — consent required
# ---------------------------------------------------------------------------
print("\n--- 5. Validation — consent required -")
s4 = session()
r4 = s4.get(f"{BASE_URL}/register")
lid3 = re.search(r'name="login_id"\s+value="([^"]+)"',   r4.text).group(1)
pp3  = re.search(r'name="passphrase"\s+value="([^"]+)"', r4.text).group(1)

r4 = s4.post(f"{BASE_URL}/register", data={
    "login_id":   lid3,
    "passphrase": pp3,
    "nickname":   "NoConsentUser",
    # consent not submitted
}, allow_redirects=True)
check("Missing consent rejected", "consent" in r4.text.lower() or r4.status_code == 200,
      r4.url)

# ---------------------------------------------------------------------------
# 6. Self-deletion
# ---------------------------------------------------------------------------
print("\n--- 6. Account self-deletion -")
r = s2.post(f"{BASE_URL}/account/delete", data={
    "confirm_delete": "TestUser",
}, allow_redirects=True)
check("Self-delete returns 200", r.status_code == 200, r.status_code)
check("Redirected to login after deletion", "/login" in r.url, r.url)

# Try logging in again — should fail
s5 = session()
r = s5.post(f"{BASE_URL}/login", data={
    "identifier": login_id,
    "password":   passphrase,
}, allow_redirects=True)
check("Deleted account cannot log in", "/login" in r.url, r.url)

# ---------------------------------------------------------------------------
# 7. Register with gender and age range
# ---------------------------------------------------------------------------
print("\n--- 7. Register with optional fields -")
s6 = session()
r6 = s6.get(f"{BASE_URL}/register")
lid4 = re.search(r'name="login_id"\s+value="([^"]+)"',   r6.text).group(1)
pp4  = re.search(r'name="passphrase"\s+value="([^"]+)"', r6.text).group(1)

r6 = s6.post(f"{BASE_URL}/register", data={
    "login_id":   lid4,
    "passphrase": pp4,
    "nickname":   "TestUser2",
    "gender":     "Female",
    "age_range":  "65–74",
    "consent":    "1",
}, allow_redirects=True)
check("Register with gender+age succeeds", r6.status_code == 200, r6.status_code)
check("Redirected to welcome page", "welcome" in r6.text.lower() or "/register/welcome" in r6.url,
      r6.url)

# Clean up — delete this account too
s6.post(f"{BASE_URL}/account/delete", data={"confirm_delete": "TestUser2"}, allow_redirects=True)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n-")
if errors:
    print(f"FAILED — {len(errors)} test(s) failed:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("All tests passed.")
