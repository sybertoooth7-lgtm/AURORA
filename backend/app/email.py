"""Outbound transactional email.

Provider-agnostic: talks plain SMTP, so it works with Gmail, SendGrid,
Mailgun, Postmark, AWS SES's SMTP interface, or a self-hosted relay --
whichever you set up first. If SMTP_HOST isn't configured (e.g. local dev,
or before you've picked a provider), messages are logged instead of sent,
so the password-reset flow stays fully testable without real credentials.
"""

import smtplib
from email.message import EmailMessage

from app.config import get_settings
from app.logging_conf import get_logger

logger = get_logger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()

    if not settings.SMTP_HOST:
        logger.info(
            "SMTP not configured -- logging email instead of sending",
            extra_keys={"to": to, "subject": subject},
        )
        logger.info(body)
        return

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)

    logger.info("Email sent", extra_keys={"to": to, "subject": subject})


def send_password_reset_email(to: str, reset_url: str) -> None:
    settings = get_settings()
    ttl_minutes = settings.PASSWORD_RESET_TOKEN_TTL_SECONDS // 60
    send_email(
        to=to,
        subject="Reset your AURORA password",
        body=(
            "Someone requested a password reset for this account.\n\n"
            f"Reset it here: {reset_url}\n\n"
            f"This link expires in {ttl_minutes} minutes and can only be used once. "
            "If you didn't request this, you can ignore this email -- your "
            "password won't change."
        ),
    )
