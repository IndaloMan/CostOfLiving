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




def send_upload_notification(app, receipt, shopper_nickname, admin_email):
    """Notify admin that a new receipt has been uploaded and is awaiting review."""
    if not config.MAIL_ENABLED:
        log.info("MAIL not configured - skipping upload notification")
        return
    try:
        from flask_mail import Message
        from . import mail
        NL = chr(10)
        company_name = receipt.company.display_name if receipt.company else "Unknown company"
        receipt_date = receipt.receipt_date.strftime("%d %b %Y") if receipt.receipt_date else "unknown date"
        total = "€{:.2f}".format(receipt.total_amount) if receipt.total_amount else "unknown total"
        review_url = "https://receipts.ego2.net/scan/review/{}".format(receipt.id)

        body = (
            "A new receipt has been uploaded by {shopper}.{nl}{nl}"
            "  Company : {company}{nl}"
            "  Date    : {date}{nl}"
            "  Total   : {total}{nl}{nl}"
            "Review it here: {url}{nl}"
        ).format(shopper=shopper_nickname, company=company_name, date=receipt_date,
                 total=total, url=review_url, nl=NL)

        html = (
            "<div style='font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:480px;'>"
            "<p><strong>{shopper}</strong> uploaded a receipt for review.</p>"
            "<table style='border-collapse:collapse;margin:1em 0;'>"
            "<tr><td style='padding:4px 12px 4px 0;font-weight:600;color:#555;'>Company</td>"
            "<td style='padding:4px 0;'>{company}</td></tr>"
            "<tr><td style='padding:4px 12px 4px 0;font-weight:600;color:#555;'>Date</td>"
            "<td style='padding:4px 0;'>{date}</td></tr>"
            "<tr><td style='padding:4px 12px 4px 0;font-weight:600;color:#555;'>Total</td>"
            "<td style='padding:4px 0;'>{total}</td></tr>"
            "</table>"
            "<p><a href='{url}' style='background:#2980b9;color:white;padding:8px 18px;"
            "border-radius:5px;text-decoration:none;font-weight:600;'>Review Receipt</a></p>"
            "</div>"
        ).format(shopper=shopper_nickname, company=company_name, date=receipt_date,
                 total=total, url=review_url)

        msg = Message(
            subject="New receipt: {} by {}".format(company_name, shopper_nickname),
            recipients=[admin_email],
            body=body,
            html=html,
        )
        with app.app_context():
            mail.send(msg)
        log.info("UPLOAD NOTIFY sent to {} for receipt#{}".format(admin_email, receipt.id))
    except Exception as e:
        log.error("UPLOAD NOTIFY failed for receipt#{}: {}".format(receipt.id, e))


def send_password_reset_email(app, email, nickname, token):
    """Send a password reset link to the user."""
    if not config.MAIL_ENABLED:
        log.info("MAIL not configured - skipping password reset email")
        return False
    try:
        from flask_mail import Message
        NL = chr(10)
        reset_url = "https://receipts.ego2.net/reset-password/{}".format(token)

        body = (
            "Hi {name},{nl}{nl}"
            "We received a request to reset your password.{nl}{nl}"
            "Click the link below to set a new password (valid for 1 hour):{nl}"
            "{url}{nl}{nl}"
            "If you did not request this, you can safely ignore this email.{nl}"
        ).format(name=nickname, url=reset_url, nl=NL)

        html = (
            "<div style='font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:480px;'>"
            "<p>Hi {name},</p>"
            "<p>We received a request to reset your password for the "
            "<strong>Cost of Living Tracker</strong>.</p>"
            "<p>Click the button below to set a new password. "
            "This link is valid for <strong>1 hour</strong>.</p>"
            "<p><a href='{url}' style='background:#2980b9;color:white;padding:8px 18px;"
            "border-radius:5px;text-decoration:none;font-weight:600;'>Reset My Password</a></p>"
            "<p style='font-size:12px;color:#888;margin-top:1.5em;'>"
            "If you did not request this, you can safely ignore this email.</p>"
            "</div>"
        ).format(name=nickname, url=reset_url)

        msg = Message(
            subject="Reset your Cost of Living Tracker password",
            recipients=[email],
            body=body,
            html=html,
        )
        with app.app_context():
            mail.send(msg)
        log.info("PASSWORD RESET EMAIL sent to {}".format(email))
        return True
    except Exception as e:
        log.error("PASSWORD RESET EMAIL failed for {}: {}".format(email, e))
        return False
