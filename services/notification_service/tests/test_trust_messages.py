"""Customer trust events: extra charges to approve, the answer, free fixes, and SOS alerts to every admin."""

import pytest

from app.core.events import render
from app.models.notification import DeviceToken
from tests.test_fallbacks import CONTACTS, DATA, client, notify  # noqa: F401  (client is a fixture)


def test_extra_charges_wording():
    asked = render("booking.extras_requested", "customer", {**DATA, "total": "350.00"})
    assert asked == (
        "Approve extra charges?",
        "The shop asks for ₹350.00 more for booking BK-7. Nothing is charged unless you approve it in the app.",
    )
    for role in ("shop", "provider"):
        title, body = render("booking.extras_decided", role, {**DATA, "decision": "declined", "total": "350.00"})
        assert title == "Extra charges declined"
        assert body == "The customer declined the extra charges of ₹350.00 for booking BK-7."


def test_a_free_fix_tells_the_shop_it_costs_nothing():
    line = "Free fix under your guarantee for booking BK-1: no charge."
    _, body = render("booking.created", "shop", {**DATA, "rework": True, "rework_line": line})
    assert body == f"Haircut booked for 24 Oct, 10:30 AM. Booking BK-7. {line}"
    # An ordinary booking reads as before.
    assert render("booking.created", "shop", DATA)[1] == "Haircut booked for 24 Oct, 10:30 AM. Booking BK-7."


SOS = {
    "alert_id": "a1",
    "booking_id": "b1",
    "booking_number": "BK-7",
    "role": "customer",
    "raised_at": "24 Oct, 10:42 AM",
    "location": "12.97160, 77.59460",
    "note": "Call me on 9876543210",
}


def test_sos_wording_never_carries_a_number():
    title, body = render("safety.sos", "admin", SOS)
    assert title == "SOS: someone needs help"
    assert "customer of booking BK-7 at 24 Oct, 10:42 AM" in body and "12.97160, 77.59460" in body
    assert "112" in body and "9876543210" not in body


@pytest.mark.asyncio
async def test_every_admin_gets_an_sos_by_email_even_with_the_app(client):  # noqa: F811
    CONTACTS["adm-1"] = {"phone": "+919800000001", "email": "adm1@example.com"}
    CONTACTS["adm-2"] = {"phone": None, "email": "adm2@example.com"}
    try:
        async with client.factory() as db:
            db.add(DeviceToken(user_id="adm-1", token="device-a", platform="android"))
            await db.commit()
        out = await notify(
            client, "safety.sos", [{"user_id": "adm-1", "role": "admin"}, {"user_id": "adm-2", "role": "admin"}], SOS
        )
        assert out == {"created": 2}
        emails = sorted((to, subject) for channel, to, subject, _ in client.sent if channel == "email")
        assert emails == [
            ("adm1@example.com", "AlakhService: SOS: someone needs help"),
            ("adm2@example.com", "AlakhService: SOS: someone needs help"),
        ]
        assert all(channel == "email" for channel, *_ in client.sent)  # never an SMS
        body = client.sent[0][3]
        assert "admin dashboard" in body and "9876543210" not in body
    finally:
        CONTACTS.pop("adm-1")
        CONTACTS.pop("adm-2")


@pytest.mark.asyncio
async def test_shop_owners_get_the_customers_answer_by_email(client):  # noqa: F811
    data = {**DATA, "decision": "approved", "total": "350.00"}
    await notify(client, "booking.extras_decided", [{"user_id": "owner", "role": "shop"}], data)
    [(channel, to, subject, body)] = client.sent
    assert (channel, to, subject) == ("email", "owner@example.com", "AlakhService: Extra charges approved")
    # A customer asked to approve extras has the app: no email or SMS for it.
    client.sent.clear()
    async with client.factory() as db:
        db.add(DeviceToken(user_id="cust", token="device-c", platform="android"))
        await db.commit()
    await notify(
        client, "booking.extras_requested", [{"user_id": "cust", "role": "customer"}], {**DATA, "total": "1.00"}
    )
    assert client.sent == []
