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

        body = f"""Hi {nickname},

Welcome to the Cost of Living Tracker!

Your login credentials are below — please keep them somewhere safe.

  Login ID : {login_id}
  Password : {password}
  Login URL: {login_url}

You can change your password at any time from the Password link in the nav bar.

"""

        msg = Message(
            subject="Your Cost of Living Tracker account",
            recipients=[email],
            body=body,
        )

        with app.app_context():
            mail.send(msg)

        log.info(f"WELCOME EMAIL sent to {email} ({nickname})")

    except Exception as e:
        log.error(f"WELCOME EMAIL failed for {email}: {e}")
