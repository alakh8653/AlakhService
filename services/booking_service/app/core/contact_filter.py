"""Hides contact details people write to each other, so a customer and a shop stay on the platform.

Phone numbers (Indian formats: +91, a leading 0, 10 digits from 6-9, digits spaced or dashed apart, or
spelled out as words), email addresses, UPI handles ("ravi@okaxis") and messaging-app links or names
(WhatsApp, Telegram) are replaced with MASK. What was found is returned too, so the message can be
flagged for review. Deliberately simple: it catches the usual ways of sharing a number, not every one.
"""

import re
from dataclasses import dataclass, field
from typing import List

MASK = "[hidden for your safety]"

PHONE = "phone"
EMAIL = "email"
UPI = "upi"
MESSAGING_APP = "messaging_app"

# An email or a UPI handle: something@domain, the domain with or without dots ("@gmail.com", "@ybl").
# "(at)" and "[at]" stand in for "@" too.
_AT = r"(?:@|\s*[(\[]at[)\]]\s*)"
_DOT = r"(?:\.|\s*[(\[]dot[)\]]\s*)"
_HANDLE = re.compile(rf"[\w.+-]+{_AT}[A-Za-z][\w-]*(?:{_DOT}[A-Za-z][\w-]*)*", re.I)
# Messaging links (wa.me/919876543210, t.me/name) and the apps' names.
_LINK = re.compile(r"\b(?:https?://)?(?:wa\.me|api\.whatsapp\.com|chat\.whatsapp\.com|t\.me|telegram\.me)/\S*", re.I)
_APP = re.compile(r"\b(?:whats\s?app|watsapp|whatsap|telegram)\b", re.I)
# Digits with up to three separators between each (spaces, dashes, dots, brackets, slashes).
_DIGITS = re.compile(r"\+?\d(?:[\s.\-()/]{0,3}\d)+")
_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
# Eight or more digits spelled out (or mixed with digits): "nine eight seven six five ...".
_SPELLED = re.compile(r"\b(?:" + "|".join(_WORDS) + r"|\d)(?:[\s,.-]+(?:" + "|".join(_WORDS) + r"|\d)){7,}\b", re.I)


@dataclass
class Filtered:
    text: str
    # What was hidden, each kind once, in the order found.
    found: List[str] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return bool(self.found)


def _looks_like_phone(run: str) -> bool:
    digits = re.sub(r"\D", "", run)
    if len(digits) >= 11:
        # +91 or 0 before a mobile number, a landline with its code, or two numbers run together.
        return True
    # A mobile number (6-9...) or a landline with its STD code (0...); a date and hour ("2026-10-19 10")
    # starts with neither.
    return len(digits) == 10 and digits[0] in "06789"


def mask_contact(text: str) -> Filtered:
    found: List[str] = []

    def note(kind: str) -> None:
        if kind not in found:
            found.append(kind)

    def link(m: re.Match) -> str:
        note(MESSAGING_APP)
        return MASK

    def handle(m: re.Match) -> str:
        value = m.group(0)
        domain = re.split(_AT, value, maxsplit=1, flags=re.I)[-1]
        note(EMAIL if re.search(_DOT, domain, re.I) else UPI)
        return MASK

    def digits(m: re.Match) -> str:
        if not _looks_like_phone(m.group(0)):
            return m.group(0)
        note(PHONE)
        return MASK

    def spelled(m: re.Match) -> str:
        tokens = re.split(r"[\s,.-]+", m.group(0).lower())
        number = "".join(_WORDS.get(t, t) for t in tokens if t)
        if len(number) < 8 or number.isdigit() and not any(t in _WORDS for t in tokens):
            return m.group(0)  # plain digits are the digit rule's business
        note(PHONE)
        return MASK

    text = _LINK.sub(link, text)
    text = _HANDLE.sub(handle, text)
    text = _DIGITS.sub(digits, text)
    text = _SPELLED.sub(spelled, text)
    text = _APP.sub(link, text)
    return Filtered(text, found)
