"""
sms_utils.py – GSM-7 sanitization and SMS truncation utilities.

Used by both llm_service.py and twilio_service.py to ensure
every outbound SMS is GSM-7 safe and within the 160-character limit.
"""

# GSM-7 basic character set
_GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ ÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "ÄÖÑܧ¿abcdefghijklmnopqrstuvwxyz"
    "äöñüà"
)
_GSM7_EXT = set("^{}\\[~]|€")
_GSM7 = _GSM7_BASIC | _GSM7_EXT

# Common non-GSM-7 replacements (smart quotes, dashes, etc.)
_REPLACE = {
    "\u2018": "'", "\u2019": "'", "\u201C": '"', "\u201D": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00A0": " ",
}


def sanitize_gsm7(text: str) -> str:
    """Replace non-GSM-7 characters with safe ASCII equivalents."""
    for o, r in _REPLACE.items():
        text = text.replace(o, r)
    return "".join(c if c in _GSM7 else " " for c in text)


def truncate_sms(text: str, limit: int = 155) -> str:
    """Truncate text to *limit* characters on a word boundary."""
    if len(text) <= limit:
        return text
    t = text[:limit]
    sp = t.rfind(" ")
    if sp > limit - 30:
        t = t[:sp]
    return t.rstrip()


def safe_sms(text: str, limit: int = 155) -> str:
    """Sanitize and truncate in one call – ready to send."""
    return truncate_sms(sanitize_gsm7(text), limit)
