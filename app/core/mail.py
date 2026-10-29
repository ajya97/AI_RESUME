"""Minimal SMTP sender. Only used when MAIL_SERVER / MAIL_FROM are configured."""

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def mail_configured() -> bool:
    c = current_app.config
    return bool(c.get("MAIL_SERVER") and c.get("MAIL_FROM"))


def send_email(to: str, subject: str, body: str) -> None:
    c = current_app.config
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = c["MAIL_FROM"], to, subject
    msg.set_content(body)
    with smtplib.SMTP(c["MAIL_SERVER"], c["MAIL_PORT"], timeout=10) as smtp:
        if c.get("MAIL_USE_TLS"):
            smtp.starttls(context=ssl.create_default_context())
        if c.get("MAIL_USERNAME"):
            smtp.login(c["MAIL_USERNAME"], c.get("MAIL_PASSWORD") or "")
        smtp.send_message(msg)
