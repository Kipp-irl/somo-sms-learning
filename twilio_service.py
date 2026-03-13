"""
twilio_service.py – Wrapper around the Twilio REST API for SMS.

Handles client initialisation and exposes a simple send_sms helper that the
rest of the application can call without touching SDK internals.

Every outbound message is automatically GSM-7 sanitised and truncated
to stay within a single 160-character SMS segment.
"""

import os
from datetime import datetime, timezone, timedelta

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

    Tries Messaging Service SID first, falls back to phone number on failure.
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

    msid = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")
    phone = os.getenv("TWILIO_PHONE_NUMBER", "")

    # Determine send order: try specified sender, then messaging service, then phone
    attempts = []
    if sender:
        attempts.append({"from_": sender, "body": message, "to": to})
    else:
        if msid:
            attempts.append({"messaging_service_sid": msid, "body": message, "to": to})
        if phone:
            attempts.append({"from_": phone, "body": message, "to": to})

    if not attempts:
        print(f"[TWILIO] No sender configured (no MESSAGING_SERVICE_SID or PHONE_NUMBER)")
        return {"error": "No Twilio sender configured"}

    last_error = None
    for i, kwargs in enumerate(attempts):
        try:
            msg = client.messages.create(**kwargs)
            via = kwargs.get("from_") or kwargs.get("messaging_service_sid", "")
            print(f"[TWILIO] SMS sent to {to} via {via}: sid={msg.sid}, status={msg.status}")
            return {"status": msg.status, "sid": msg.sid}
        except Exception as exc:
            last_error = exc
            via = kwargs.get("from_") or kwargs.get("messaging_service_sid", "")
            print(f"[TWILIO] Attempt {i+1} failed (via {via}): {exc}")
            # Try next method
            continue

    print(f"[TWILIO] All send attempts failed for {to}: {last_error}")
    return {"error": str(last_error)}


# ---------------------------------------------------------------------------
# Inbound message polling (no webhook/tunnel needed)
# ---------------------------------------------------------------------------

def fetch_inbound_messages(since_minutes: int = 2) -> list[dict]:
    """
    Fetch recent inbound SMS messages from Twilio's API.

    Returns a list of dicts with keys: sid, from_number, body, date_sent.
    """
    client = _get_client()
    if client is None:
        return []

    phone = os.getenv("TWILIO_PHONE_NUMBER", "")
    if not phone:
        return []

    since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

    try:
        messages = client.messages.list(
            to=phone,
            date_sent_after=since,
            limit=20,
        )
        results = []
        for m in messages:
            if m.direction == "inbound":
                results.append({
                    "sid": m.sid,
                    "from_number": m.from_,
                    "body": m.body or "",
                    "date_sent": m.date_sent,
                })
        if results:
            print(f"[TWILIO] Polled {len(results)} inbound message(s)")
        return results
    except Exception as exc:
        print(f"[TWILIO] Polling error: {exc}")
        return []
