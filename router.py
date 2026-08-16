"""
Cheap rule-based routing before any model is touched. Only ambiguous
messages fall through to a Flash-Lite classification call.
"""
import re

TRIVIAL_PATTERNS = [
    r"^\s*(hi|hey|hello|yo|sup)\s*!?\s*$",
    r"^\s*(thanks|thank you|ty|cheers)\s*!?\s*$",
    r"^\s*(bye|goodnight|gn|cya)\s*!?\s*$",
]

TRIVIAL_RESPONSES = {
    "greeting": "Hey. What do you need?",
    "thanks": "Anytime.",
    "farewell": "Later.",
}

COMMAND_PREFIX = "/"


def classify_trivial(text: str) -> str | None:
    """Returns a canned response key if this is trivial, else None."""
    lowered = text.strip().lower()
    for pattern in TRIVIAL_PATTERNS[:1]:
        if re.match(pattern, lowered):
            return "greeting"
    for pattern in TRIVIAL_PATTERNS[1:2]:
        if re.match(pattern, lowered):
            return "thanks"
    for pattern in TRIVIAL_PATTERNS[2:3]:
        if re.match(pattern, lowered):
            return "farewell"
    return None


def is_command(text: str) -> bool:
    return text.strip().startswith(COMMAND_PREFIX)
