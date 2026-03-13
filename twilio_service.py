"""
twilio_service.py – Wrapper around the Twilio REST API for SMS.

Handles client initialisation and exposes a simple send_sms helper that the
rest of the application can call without touching SDK internals.

Every outbound message is automatically GSM-7 sanitised and truncated
to stay within a single 160-character SMS segment.
"""

import os

from sms_utils import safe_sms

# ---------------------------------------------------------------------------
# Client initialisation (lazy – only created when first needed)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    global _client
    if _client is None:
        sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        token = os.getenv("TWILIO_AUTH_TOKEN", "")
        if not sid or not token:
            return None
        from twilio.rest import Client
        _client = Client(sid, token)
    return _client


# ---------------------------------------------------------------------------
# Simulator capture mechanism
# ---------------------------------------------------------------------------
_capture_mode = False
_captured_messages: list[str] = []


def set_capture_mode(enabled: bool):
    """Enable or disable SMS capture mode for simulation."""
    global _capture_mode, _captured_messages
    _capture_mode = enabled
    if enabled:
        _captured_messages = []


def get_captured_messages() -> list[str]:
    """Return messages captured during simulation and clear the buffer."""
    global _captured_messages
    msgs = list(_captured_messages)
    _captured_messages = []
    return msgs


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def send_sms(to: str, message: str, sender: str | None = None) -> dict:
    """
    Send an SMS through Twilio (or capture it in simulation mode).

    The message is automatically sanitised (GSM-7 safe) and truncated to
    155 characters before dispatch so callers never need to worry about
    encoding issues or concatenation costs.

    Parameters
    ----------
    to : str
        Recipient phone number in E.164 format (e.g. "+254712345678").
    message : str
        The text body (will be sanitised and truncated automatically).
    sender : str | None
        Optional Twilio phone number to send from. Falls back to
        messaging service SID if not provided.

    Returns
    -------
    dict
        Status info from the Twilio API, or capture confirmation.
    """
    message = safe_sms(message)

    # Simulation capture mode: store message instead of sending
    if _capture_mode:
        _captured_messages.append(message)
        print(f"[SIM] Captured SMS to {to}: {message}")
        return {"status": "captured", "sid": "SIM_MODE"}

    client = _get_client()
    if client is None:
        print(f"[TWILIO] Client not configured – SMS to {to} skipped")
        return {"error": "Twilio client not configured (missing credentials)"}

    try:
        kwargs = {
            "body": message,
            "to": to,
        }
        if sender:
            kwargs["from_"] = sender
        elif os.getenv("TWILIO_MESSAGING_SERVICE_SID", ""):
            kwargs["messaging_service_sid"] = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")
        elif os.getenv("TWILIO_PHONE_NUMBER", ""):
            kwargs["from_"] = os.getenv("TWILIO_PHONE_NUMBER", "")

        msg = client.messages.create(**kwargs)
        print(f"[TWILIO] SMS sent to {to}: sid={msg.sid}, status={msg.status}")
        return {"status": msg.status, "sid": msg.sid}
    except Exception as exc:
        print(f"[TWILIO] Failed to send SMS to {to}: {exc}")
        return {"error": str(exc)}
