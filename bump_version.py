#!/usr/bin/env python3
"""
bump_version.py

Called by .git/hooks/pre-commit to auto-increment APP_VERSION in config.py
and insert a dated entry into the Release Notes section of README.md.

The README entry lists the staged source files so there is always context
about what changed. Replace the file list with proper descriptions before
pushing, or leave it as-is — it is better than a blank entry.
"""

import re
import subprocess
import sys
from datetime import date

CONFIG_FILE = "config.py"
README_FILE = "README.md"


def main():
    # ------------------------------------------------------------------ #
    # 1. Read and bump version in config.py                               #
    # ------------------------------------------------------------------ #
    with open(CONFIG_FILE, encoding="utf-8") as f:
        config_text = f.read()

    m = re.search(r'APP_VERSION\s*=\s*["\'](\d+)\.(\d+)["\']', config_text)
    if not m:
        print("bump_version: APP_VERSION not found in config.py — skipping")
        return 0

    major, minor = int(m.group(1)), int(m.group(2))
    old_version = f"{major}.{minor}"
    new_version = f"{major}.{minor + 1}"

    new_config = re.sub(
        r'(APP_VERSION\s*=\s*["\'])\d+\.\d+(["\'])',
        rf"\g<1>{new_version}\2",
        config_text,
    )
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(new_config)

    # ------------------------------------------------------------------ #
    # 2. Build a README entry                                             #
    # ------------------------------------------------------------------ #
    today = date.today()
    date_str = f"{today.day} {today.strftime('%B %Y')}"   # e.g. "3 March 2026"

    # List staged source files for context (exclude the files we're about to add)
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    staged = [
        f for f in result.stdout.strip().splitlines()
        if f.endswith((".py", ".html", ".js", ".css"))
        and f not in (CONFIG_FILE, README_FILE)
    ]
    files_note = ", ".join(staged) if staged else "see commit"

    new_section = f"### v{new_version} — {date_str}\n- {files_note}\n\n"

    # ------------------------------------------------------------------ #
    # 3. Insert into README (only if this version is not already there)  #
    # ------------------------------------------------------------------ #
    with open(README_FILE, encoding="utf-8") as f:
        readme_text = f.read()

    if f"### v{new_version}" not in readme_text:
        readme_text = readme_text.replace(
            "## Release Notes\n\n",
            f"## Release Notes\n\n{new_section}",
        )
        with open(README_FILE, "w", encoding="utf-8") as f:
            f.write(readme_text)

    # ------------------------------------------------------------------ #
    # 4. Stage both files so the bump is part of this commit             #
    # ------------------------------------------------------------------ #
    subprocess.run(["git", "add", CONFIG_FILE, README_FILE])
    print(f"bump_version: v{old_version} -> v{new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
