"""A shop's report in words: the email, and what goes to WhatsApp and to whom."""

import json

import httpx
import pytest

from app.channels.whatsapp import MSG91WhatsAppChannel
from app.core import reports
from app.services import notification_service as module
from app.services.notification_service import notification_service

REPORT = {
    "period": "monthly",
    "label": "October 2026",
    "from": "2026-10-01",
    "bookings": 12,
    "gross": 150000.5,
    "cash": 50000,
    "online": 100000.5,
    "commission": 15000,
    "gst": 2700,
    "earned": 132300.5,
    "other_income": 1000,
    "expenses": 140000,
    "profit": -6699.5,
    "tips": 200,
    "profit_change_percent": -12.5,
    "expenses_by_category": [{"category": "SPARE_PARTS", "amount": 140000}],
    "note": "Profit counts only what is recorded here.",
}


def test_amounts_use_indian_grouping_and_show_a_loss():
    assert reports._inr(1234567.5) == "₹12,34,567.50"
    assert reports._inr(999) == "₹999"
    assert reports._inr(-6699.5) == "-₹6,699.50"
    assert reports._inr(None) == "₹0"


def test_the_email_says_loss_when_it_is_a_loss_and_explains_the_trend():
    text = reports.text_body(REPORT, "Ravi <Salon>")
    assert "LOSS: -₹6,699.50" in text
    assert "Profit is down 12.5% on the period before." in text
    assert "Spare parts: ₹1,40,000" in text
    assert "Profit counts only what is recorded here." in text
    # A name is never trusted in the HTML part.
    assert "Ravi &lt;Salon&gt;" in reports.html_body(REPORT, "Ravi <Salon>")
    assert reports.subject(REPORT, "Ravi") == "Ravi: monthly report, October 2026"


def test_the_whatsapp_values_match_the_template():
    assert reports.whatsapp_values(REPORT, "Ravi Salon") == [
        "Ravi Salon",
        "October 2026",
        "12",
        "₹1,33,300.50",
        "₹1,40,000",
        "-₹6,699.50",
    ]


@pytest.mark.asyncio
async def test_whatsapp_sends_the_approved_template_to_the_owners_own_number():
    seen = {}

    def handler(request):
        seen["key"] = request.headers["authkey"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "success"})

    channel = MSG91WhatsAppChannel("key", "919000000000", "report", transport=httpx.MockTransport(handler))
    assert await channel.send("+919812345678", ["Ravi", "Oct"]) is True
    template = seen["body"]["payload"]["template"]
    assert seen["key"] == "key"
    assert seen["body"]["integrated_number"] == "919000000000"
    assert template["name"] == "report"
    assert template["to_and_components"][0]["to"] == ["919812345678"]
    assert template["to_and_components"][0]["components"]["body_2"]["value"] == "Oct"


@pytest.mark.asyncio
async def test_whatsapp_without_setup_sends_nothing_and_a_refusal_is_reported():
    assert await MSG91WhatsAppChannel("", "", "").send("+919812345678", ["x"]) is False
    refused = httpx.MockTransport(lambda r: httpx.Response(400, json={"errors": "bad template"}))
    assert await MSG91WhatsAppChannel("k", "9", "t", transport=refused).send("+919812345678", ["x"]) is False


class FakeEmail:
    def __init__(self):
        self.sent = []

    async def send(self, *args):
        self.sent.append(args)
        return True


class FakeWhatsApp:
    def __init__(self, ok=True):
        self.sent = []
        self.ok = ok

    async def send(self, to, values):
        self.sent.append((to, values))
        return self.ok


@pytest.fixture
def channels(monkeypatch):
    email, whatsapp = FakeEmail(), FakeWhatsApp()
    monkeypatch.setattr(notification_service, "_get_email", lambda: email)
    monkeypatch.setattr(notification_service, "_get_whatsapp", lambda: whatsapp)
    monkeypatch.setattr(module.settings, "SMTP_HOST", "smtp.example.com")

    async def contact(user_id):
        return {"phone": "+919812345678", "email": "owner@example.com"}

    monkeypatch.setattr(module, "fetch_contact", contact)
    return email, whatsapp


@pytest.mark.asyncio
async def test_the_report_goes_where_the_owner_chose_with_the_file_attached(channels):
    email, whatsapp = channels
    sent = await notification_service.deliver_report("u1", "Ravi", REPORT, "a,b\n", True, False)
    assert sent == ["email"]
    assert whatsapp.sent == []
    to, _subject, _text, _html, attachment = email.sent[0]
    assert to == "owner@example.com"
    assert attachment == ("alakhservice-report-monthly-2026-10-01.csv", "a,b\n")

    assert await notification_service.deliver_report("u1", "Ravi", REPORT, "", False, True) == ["whatsapp"]
    assert whatsapp.sent[0][0] == "+919812345678"


@pytest.mark.asyncio
async def test_it_says_nothing_went_out_when_nothing_did(channels, monkeypatch):
    monkeypatch.setattr(module.settings, "SMTP_HOST", "")
    monkeypatch.setattr(notification_service, "_get_whatsapp", lambda: FakeWhatsApp(ok=False))
    assert await notification_service.deliver_report("u1", "Ravi", REPORT, "", True, True) == []


@pytest.mark.asyncio
async def test_the_email_really_has_the_words_and_the_file(monkeypatch):
    from email import message_from_bytes
    from email.policy import default

    from app.channels import email as email_module

    sent = []

    async def fake_send(msg, **kwargs):
        sent.append(msg)

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)
    channel = email_module.EmailChannel("smtp", 587, "", "", "noreply@alakhservice.com", "AlakhService")
    assert await channel.send("owner@example.com", "Report", "Profit", "<b>Profit</b>", ("report.csv", "a,b\n")) is True
    parsed = message_from_bytes(sent[0].as_bytes(), policy=default)
    assert (parsed["To"], parsed["Subject"]) == ("owner@example.com", "Report")
    assert parsed.get_body(("plain",)).get_content().strip() == "Profit"
    assert "<b>Profit</b>" in parsed.get_body(("html",)).get_content()
    attachment = next(parsed.iter_attachments())
    assert attachment.get_filename() == "report.csv"
    assert attachment.get_content() == b"a,b\n"

    # Other messages stay as they were, with no attachment.
    await channel.send("owner@example.com", "Hello", "Plain")
    assert list(message_from_bytes(sent[1].as_bytes(), policy=default).iter_attachments()) == []
