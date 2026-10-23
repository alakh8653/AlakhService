"""The money rules on their own: commission and GST rounding, the cancellation policy, invoice series."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core import money

D = Decimal
NOW = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)


def test_commission_and_gst_on_it_for_a_booking():
    s = money.split(49900, D("10"), D("18"))
    # 10% of ₹499 is ₹49.90; 18% GST on that is ₹8.982, rounded to ₹8.98.
    assert (s.commission_cents, s.gst_cents, s.net_cents, s.platform_cents) == (4990, 898, 44012, 5888)
    assert s.gross_cents == s.net_cents + s.commission_cents + s.gst_cents


@pytest.mark.parametrize(
    "gross, pct, gst, commission, tax",
    [
        (12345, "10", "18", 1235, 222),  # 1234.5 paise rounds up; 222.3 down
        (250, "10", "18", 25, 5),  # 4.5 paise of GST rounds half up to 5
        (249, "10", "18", 25, 5),  # 24.9 paise of commission rounds to 25, so GST is 4.5 -> 5 again
        (1, "10", "18", 0, 0),
        (100000, "7.5", "18", 7500, 1350),
        (0, "10", "18", 0, 0),
    ],
)
def test_amounts_are_rounded_half_up_to_the_paisa(gross, pct, gst, commission, tax):
    s = money.split(gross, D(pct), D(gst))
    assert s.commission_cents == commission
    assert s.gst_cents == tax
    assert s.net_cents == gross - commission - tax


def test_what_the_platform_owes_the_shop_depends_on_who_collected():
    s = money.split(20000, D("10"), D("18"))
    assert money.payout_cents(s, "ONLINE") == 20000 - 2000 - 360
    # Paid at the shop: the shop holds the money and owes commission and GST.
    assert money.payout_cents(s, "CASH") == -2360


@pytest.mark.parametrize(
    "by, hours_before, fee_pct, refund, fee",
    [
        ("shop", 0.5, "50", 10000, 0),  # a shop cancelling always refunds in full
        ("admin", -1, "50", 10000, 0),
        ("customer", 3, "50", 10000, 0),  # in time
        ("customer", 2, "50", 10000, 0),  # exactly CANCEL_FREE_HOURS before is still in time
        ("customer", 1.5, "0", 10000, 0),  # late, but the default fee is nothing
        ("customer", 1.5, "10", 9000, 1000),
        ("customer", 1.5, "33.333", 6667, 3333),
        ("customer", -2, "150", 0, 10000),  # never more than was paid
    ],
)
def test_cancellation_refund_policy(by, hours_before, fee_pct, refund, fee):
    scheduled = NOW + timedelta(hours=hours_before)
    out = money.cancel_refund(10000, by, scheduled, NOW, 2, D(fee_pct))
    assert (out.refund_cents, out.fee_cents) == (refund, fee)


def test_a_customer_cancel_without_a_scheduled_time_is_refunded_in_full():
    assert money.cancel_refund(5000, "customer", None, NOW, 2, D("50")).refund_cents == 5000


def test_naive_times_are_taken_as_utc():
    scheduled = (NOW + timedelta(hours=1)).replace(tzinfo=None)
    assert money.cancel_refund(10000, "customer", scheduled, NOW, 2, D("10")).fee_cents == 1000


def test_financial_year_runs_april_to_march_in_india():
    # 31 March 23:30 in India is still the old year; 1 April 00:30 is the new one.
    assert money.financial_year(datetime(2026, 3, 31, 18, 0, tzinfo=timezone.utc)) == "2025-26"
    assert money.financial_year(datetime(2026, 3, 31, 19, 0, tzinfo=timezone.utc)) == "2026-27"
    assert money.financial_year(datetime(2026, 10, 23, tzinfo=timezone.utc)) == "2026-27"
    assert money.financial_year(datetime(2099, 12, 1, tzinfo=timezone.utc)) == "2099-00"


def test_invoice_numbers():
    series = money.invoice_series("ALK", NOW)
    assert series == "ALK/2026-27"
    assert money.invoice_number(series, 123) == "ALK/2026-27/000123"
    assert money.rupees(44012) == 440.12
