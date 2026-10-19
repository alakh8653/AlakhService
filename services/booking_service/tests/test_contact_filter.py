"""Contact details written into a chat message (or a booking's notes) are hidden."""

import pytest

from app.core.contact_filter import EMAIL, MASK, MESSAGING_APP, PHONE, UPI, mask_contact


@pytest.mark.parametrize(
    "text",
    [
        "call me on 9876543210",
        "my number +91 98765 43210",
        "+919876543210",
        "91-98765-43210",
        "098765 43210",
        "9876-543-210",
        "9 8 7 6 5 4 3 2 1 0",
        "(987) 654-3210",
        "98.76.54.32.10",
        "080 2345 6789",
        "nine eight seven six five four three two one zero",
        "Nine, eight, seven, six, 5, 4, 3, 2, 1, 0",
        "9876543210 9123456789",
    ],
)
def test_phone_numbers_are_hidden(text):
    result = mask_contact(text)
    assert result.found == [PHONE], text
    assert MASK in result.text
    assert not any(c.isdigit() for c in result.text)


def test_the_rest_of_the_message_is_kept():
    result = mask_contact("Hi, call 98765 43210 after 5 pm please")
    assert result.text == f"Hi, call {MASK} after 5 pm please"


@pytest.mark.parametrize(
    "text,kind",
    [
        ("mail me at ravi.kumar@gmail.com", EMAIL),
        ("ravi (at) gmail (dot) com", EMAIL),
        ("ravi[at]yahoo[dot]in", EMAIL),
        ("pay to ravi@okaxis", UPI),
        ("UPI: 9876543210@ybl", UPI),
    ],
)
def test_emails_and_upi_handles_are_hidden(text, kind):
    result = mask_contact(text)
    assert kind in result.found
    assert "@" not in result.text and "gmail" not in result.text and "okaxis" not in result.text


@pytest.mark.parametrize(
    "text",
    ["ping me on WhatsApp", "whats app me", "https://wa.me/919876543210", "t.me/ravi_salon", "on telegram"],
)
def test_messaging_apps_are_hidden(text):
    result = mask_contact(text)
    assert MESSAGING_APP in result.found
    assert MASK in result.text


@pytest.mark.parametrize(
    "text",
    [
        "See you at 10:30 tomorrow",
        "Booking BK12345678 is ready",
        "That will be Rs 1500, or 2,500 with the polish",
        "Pickup on 2026-10-19 10:30",
        "Flat 402, 3rd floor, 560034",
        "I'll be there in one or two minutes",
        "Meet at 5 @ the shop",
        "@ravi thanks!",
    ],
)
def test_ordinary_messages_pass_untouched(text):
    result = mask_contact(text)
    assert (result.text, result.found, result.flagged) == (text, [], False)


def test_each_kind_is_reported_once():
    result = mask_contact("9876543210 or 9123456780, or ravi@gmail.com")
    assert result.found == [EMAIL, PHONE]
    assert result.text.count(MASK) == 3
