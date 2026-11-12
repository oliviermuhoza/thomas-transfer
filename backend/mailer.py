"""Transactional email over plain SMTP (Python stdlib only).

Configuration comes from the environment so nothing secret lives in the repo:

  TT_SMTP_HOST   smtp.example.com           (required to send)
  TT_SMTP_PORT   587
  TT_SMTP_USER   mailbox user               (optional if the relay is open)
  TT_SMTP_PASSWORD
  TT_SMTP_FROM   TOM Safaris <no-reply@example.com>
  TT_SMTP_SECURITY  starttls | ssl | none   (default: starttls)

When no host is configured nothing is sent and the caller decides what to log.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


def settings():
    return {
        "host": os.environ.get("TT_SMTP_HOST", "").strip(),
        "port": int(os.environ.get("TT_SMTP_PORT", "587") or 587),
        "user": os.environ.get("TT_SMTP_USER", "").strip(),
        "password": os.environ.get("TT_SMTP_PASSWORD", ""),
        "sender": os.environ.get("TT_SMTP_FROM", "").strip(),
        "security": os.environ.get("TT_SMTP_SECURITY", "starttls").strip().lower(),
    }


def configured():
    config = settings()
    return bool(config["host"] and (config["sender"] or config["user"]))


def send_email(to_email, subject, body):
    """Send one plain-text message. Raises on transport errors."""
    config = settings()
    if not config["host"]:
        raise RuntimeError("TT_SMTP_HOST is not configured.")

    message = EmailMessage()
    message["From"] = config["sender"] or config["user"]
    message["Reply-To"] = "tomsafaris@gmail.com"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    if config["security"] == "ssl":
        server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=15)
    else:
        server = smtplib.SMTP(config["host"], config["port"], timeout=15)
    try:
        if config["security"] == "starttls":
            server.starttls(context=ssl.create_default_context())
        if config["user"]:
            server.login(config["user"], config["password"])
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            pass
