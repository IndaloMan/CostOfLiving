import logging
import config

log = logging.getLogger(__name__)


def send_welcome_email(app, email, nickname, login_id, password):
    """Send a welcome email with login credentials.  Silently logs on failure."""
    if not config.MAIL_ENABLED:
        log.info("MAIL not configured — skipping welcome email")
        return

    try:
        from flask_mail import Message
        from . import mail

        login_url = "https://receipts.ego2.net/login"

        # Plain-text fallback
        body = f"""Hi {nickname},

Welcome to the Cost of Living Tracker!

Your login credentials are below — please keep them somewhere safe.

  Login ID : {login_id}
  Password : {password}

Log in here: {login_url}

You can change your password at any time from the Password link in the nav bar.
"""

        # HTML version — URL hidden behind link text so SafeLinks doesn't sprawl
        html = f"""
<div style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:480px;">
  <p>Hi {nickname},</p>
  <p>Welcome to the <strong>Cost of Living Tracker</strong>!</p>
  <p>Your login credentials are below — please keep them somewhere safe.</p>
  <table style="border-collapse:collapse;margin:1em 0;">
    <tr>
      <td style="padding:4px 12px 4px 0;font-weight:600;color:#555;">Login ID</td>
      <td style="padding:4px 0;font-family:monospace;font-size:15px;color:#1a5276;">{login_id}</td>
    </tr>
    <tr>
      <td style="padding:4px 12px 4px 0;font-weight:600;color:#555;">Password</td>
      <td style="padding:4px 0;font-family:monospace;font-size:15px;color:#1a5276;">{password}</td>
    </tr>
  </table>
  <p>
    <a href="{login_url}" style="background:#2980b9;color:white;padding:8px 18px;border-radius:5px;text-decoration:none;font-weight:600;">
      Log in to Cost of Living Tracker
    </a>
  </p>
  <p style="font-size:12px;color:#888;margin-top:1.5em;">
    You can change your password at any time from the Password link in the nav bar.
  </p>
</div>
"""

        msg = Message(
            subject="Your Cost of Living Tracker account",
            recipients=[email],
            body=body,
            html=html,
        )

        with app.app_context():
            mail.send(msg)

        log.info(f"WELCOME EMAIL sent to {email} ({nickname})")

    except Exception as e:
        log.error(f"WELCOME EMAIL failed for {email}: {e}")
