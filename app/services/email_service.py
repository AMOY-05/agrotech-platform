try:
    import aiosmtplib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency in some environments
    aiosmtplib = None  # type: ignore[assignment]

from email.message import EmailMessage
from loguru import logger

from app.core.config import settings


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Returns True on success, False on failure.

    Never raises. A mail outage must not break the calling endpoint — and in
    the reset flow, a different response on failure would leak which email
    addresses are registered.
    """
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("SMTP not configured — skipping email send")
        return False

    message = EmailMessage()
    message["From"] = f"AgroTech Intelligence <{settings.smtp_from}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
            timeout=15,
        )
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed for {to}: {e}")
        return False


def reset_email_html(full_name: str, reset_url: str) -> str:
    name = full_name or "there"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="color:#2E7D32;margin-bottom:4px">AgroTech Intelligence</h2>
      <p>Hello {name},</p>
      <p>We received a request to reset your password. Tap the button below to
         choose a new one. This link works once and expires in 30 minutes.</p>
      <p style="text-align:center;margin:32px 0">
        <a href="{reset_url}"
           style="background:#2E7D32;color:#fff;padding:14px 28px;
                  text-decoration:none;border-radius:6px;display:inline-block">
          Reset my password
        </a>
      </p>
      <p style="font-size:13px;color:#666">
        If the button doesn't work, copy this link into your browser:<br>
        <span style="word-break:break-all">{reset_url}</span>
      </p>
      <p style="font-size:13px;color:#666">
        Didn't request this? You can safely ignore this email — your password
        will not change.
      </p>
    </div>
    """


def google_account_html(full_name: str) -> str:
    name = full_name or "there"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="color:#2E7D32;margin-bottom:4px">AgroTech Intelligence</h2>
      <p>Hello {name},</p>
      <p>You asked to reset your AgroTech password, but your account signs in
         with Google. Use the <b>Continue with Google</b> button on the login
         page instead — there's no password to reset.</p>
    </div>
    """