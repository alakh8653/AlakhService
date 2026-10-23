"""Formats of the Indian business and bank identifiers a shop gives during onboarding."""

import re
from typing import Optional

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# 2-digit state code, the holder's PAN, the registration number in that state, "Z", a check character.
GSTIN_RE = re.compile(r"^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
# Bank code, a zero, then the branch.
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
# name@handle, e.g. asha.salon@okhdfcbank
UPI_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,255}@[A-Za-z][A-Za-z0-9]{1,63}$")
ACCOUNT_NUMBER_RE = re.compile(r"^[0-9]{9,18}$")


def gstin_check_character(first14: str) -> str:
    """The 15th character of a GSTIN, computed from the first 14 (the GSTN's mod-36 checksum)."""
    total = 0
    for i, ch in enumerate(first14):
        product = _GSTIN_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _GSTIN_CHARS[(36 - total % 36) % 36]


def normalise_gstin(value: Optional[str]) -> Optional[str]:
    """Upper-cased and trimmed, or None for blank; ValueError when it is not a valid GSTIN."""
    value = (value or "").strip().upper()
    if not value:
        return None
    if not GSTIN_RE.match(value):
        raise ValueError("GSTIN must be 15 characters like 27AAPFU0939F1ZV")
    if gstin_check_character(value[:14]) != value[14]:
        raise ValueError("GSTIN check character does not match; please re-check the number")
    return value


def normalise_ifsc(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip().upper()
    if not value:
        return None
    if not IFSC_RE.match(value):
        raise ValueError("IFSC must be 11 characters like HDFC0001234")
    return value


def normalise_upi(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    if not UPI_RE.match(value):
        raise ValueError("UPI id must look like name@bank")
    return value.lower()


def normalise_account_number(value: Optional[str]) -> Optional[str]:
    value = (value or "").replace(" ", "").strip()
    if not value:
        return None
    if not ACCOUNT_NUMBER_RE.match(value):
        raise ValueError("Account number must be 9 to 18 digits")
    return value


def mask_account_number(value: Optional[str]) -> Optional[str]:
    """Only the last four digits stay readable: "XXXXXXXX1234"."""
    if not value:
        return None
    return "X" * max(len(value) - 4, 0) + value[-4:]
