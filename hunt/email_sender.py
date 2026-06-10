from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path

from hunt.utils import HuntError


def _add_attachment(message: EmailMessage, attachment_path: str) -> None:
    path = Path(attachment_path).expanduser()
    if not path.exists() or not path.is_file():
        raise HuntError(f"Attachment file not found: {path}")

    content_type, _ = mimetypes.guess_type(path)
    maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
    message.add_attachment(
        path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=path.name,
    )


def send_email(
    sender_email: str,
    app_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_path: str | None = None,
) -> None:
    if not sender_email or not app_password:
        raise HuntError(
            "SMTP credentials are missing. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in your .env file."
        )

    message = EmailMessage()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)

    if attachment_path:
        _add_attachment(message, attachment_path)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender_email, app_password)
            smtp.send_message(message)
    except smtplib.SMTPException as exc:
        raise HuntError(f"Failed to send email through Gmail SMTP: {exc}") from exc
