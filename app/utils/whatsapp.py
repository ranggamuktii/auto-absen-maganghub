"""WhatsApp notification helper via Twilio."""

import requests
from requests.auth import HTTPBasicAuth

from app.api.client import TIMEOUT
from app.config import settings
from app.utils.log import log


def send_whatsapp(text: str) -> None:
    """Send a WhatsApp message via Twilio API if credentials are set.

    Does nothing when credentials are missing, and never raises,
    so a notification failure cannot break the attendance flow.

    Args:
        text: Message text to send.
    """
    sid = settings.twilio_account_sid.strip()
    token = settings.twilio_auth_token.strip()
    to_number = settings.whatsapp_to.strip()
    from_number = settings.twilio_whatsapp_from.strip() or "+14155238886"

    if not sid or not token or not to_number:
        return

    # Normalize to Twilio WhatsApp URI format: whatsapp:+628...
    if not from_number.startswith("whatsapp:"):
        if not from_number.startswith("+"):
            from_number = f"+{from_number}"
        from_number = f"whatsapp:{from_number}"

    if not to_number.startswith("whatsapp:"):
        if not to_number.startswith("+"):
            to_number = f"+{to_number}"
        to_number = f"whatsapp:{to_number}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {
        "From": from_number,
        "To": to_number,
        "Body": text,
    }

    try:
        resp = requests.post(
            url,
            data=data,
            auth=HTTPBasicAuth(sid, token),
            timeout=TIMEOUT,
        )
        if resp.status_code >= 400:
            log(f"[WARN] Notifikasi WhatsApp Twilio gagal ({resp.status_code}): {resp.text}")
    except Exception as e:
        log(f"[WARN] Notifikasi WhatsApp Twilio error: {e}")


def notify(text: str) -> None:
    """Send a notification via WhatsApp.

    Args:
        text: Message text to send.
    """
    send_whatsapp(text)


def log_notify(text: str) -> None:
    """Log a message and send it as a WhatsApp notification.

    Args:
        text: Message text to log and send.
    """
    log(text)
    notify(text)
