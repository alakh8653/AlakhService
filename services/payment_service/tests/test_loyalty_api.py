"""Loyalty points (earned on completed bookings, spent on new ones, paid for by the platform) and referrals."""

from datetime import datetime, timezone

import pytest

from app.database import get_db
from app.main import app
from app.models.payment import LoyaltyEntry, ShopEarning
from tests import test_earnings_api
from tests.test_earnings_api import ADMIN, cancel_body, internal, rows
from tests.test_payment_access_api import auth, paid_by_razorpay

# The API client with the fakes for booking_service, shops and Razorpay (see test_earnings_api).
http = test_earnings_api.http
client = test_earnings_api.client


async def give(user_id: str, points: int, booking_id: str = "seed") -> None:
    gen = app.dependency_overrides[get_db]()
    db = await gen.__anext__()
    try:
        db.add(
            LoyaltyEntry(
                user_id=user_id,
                kind="EARN",
                points=points,
                booking_id=booking_id,
                created_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
    finally:
        await gen.aclose()


async def mine(http, user="cust"):
    resp = await http.get("/api/v1/loyalty/me", headers=auth(user))
    assert resp.status_code == 200, resp.text
    return resp.json()


def redeem(http, booking_id, price, customer="cust"):
    return internal(http, "/loyalty/redeem", {"customer_id": customer, "booking_id": booking_id, "price_cents": price})


def completed(http, booking_id, total, customer="cust", shop="shop-1"):
    return internal(
        http, f"/booking/{booking_id}/completed", {"shop_id": shop, "customer_id": customer, "total_amount": total}
    )


@pytest.mark.asyncio
async def test_points_are_earned_on_what_was_paid_and_shown_with_the_rules(http):
    resp = await completed(http, "bk-a", 49900)
    assert resp.json()["points_earned"] == 9  # 2 per Rs 100
    assert (await completed(http, "bk-a", 49900)).json()["points_earned"] == 9  # reported again: once
    me = await mine(http)
    assert (me["points"], me["value_cents"], me["redeem_max_percent"]) == (9, 900, 20)
    assert len(me["referral_code"]) == 8 and me["referral_code"] == (await mine(http))["referral_code"]
    assert [(h["kind"], h["points"], h["booking_id"]) for h in me["history"]] == [("EARN", 9, "bk-a")]
    assert (await http.get("/api/v1/loyalty/me")).status_code == 401


@pytest.mark.asyncio
async def test_points_pay_up_to_a_fifth_of_a_booking_once_and_come_back_on_cancel(http):
    await give("cust", 100)
    first = await redeem(http, "bk-1", 30000)
    assert first.json()["discount_cents"] == 6000  # 20% of Rs 300
    assert (await redeem(http, "bk-1", 30000)).json()["discount_cents"] == 6000  # the same booking: no more
    assert (await mine(http))["points"] == 40
    assert (await redeem(http, "bk-other", 1000, customer="nobody")).json()["discount_cents"] == 0

    await internal(http, "/booking/bk-1/cancelled", cancel_body("customer", 48))
    assert (await mine(http))["points"] == 100
    await internal(http, "/booking/bk-1/cancelled", cancel_body("customer", 48))  # retried: once
    assert (await mine(http))["points"] == 100

    await redeem(http, "bk-never-made", 30000)
    assert (await internal(http, "/loyalty/release", {"booking_id": "bk-never-made"})).json()["points_returned"] == 60
    assert (await mine(http))["points"] == 100
    assert (
        await internal(http, "/loyalty/redeem", {"customer_id": "c", "booking_id": "b", "price_cents": 1}, key="x")
    ).status_code == 401


@pytest.mark.asyncio
async def test_the_platform_pays_for_points_so_the_shop_earns_the_full_price(http):
    # Online: Rs 250 listed, Rs 50 of points, Rs 200 paid (bk-2's total).
    await give("cust", 100)
    assert (await redeem(http, "bk-2", 25000)).json()["discount_cents"] == 5000
    await paid_by_razorpay(http, "key-loyal-1", "bk-2")
    resp = await completed(http, "bk-2", 20000)
    earning = resp.json()["earning"]
    assert (earning["gross_cents"], earning["commission_cents"], earning["gst_cents"]) == (25000, 2500, 450)
    assert earning["payout_cents"] == 22050  # more than the Rs 200 the platform collected
    assert resp.json()["points_earned"] == 4  # on the Rs 200 the customer paid

    # Cash: Rs 300 listed, Rs 60 of points, Rs 240 handed to the shop.
    await give("cust2", 100)
    await redeem(http, "bk-cash", 30000, customer="cust2")
    cash = (await completed(http, "bk-cash", 24000, customer="cust2")).json()["earning"]
    assert (cash["collection"], cash["gross_cents"], cash["commission_cents"], cash["gst_cents"]) == (
        "CASH",
        30000,
        3000,
        540,
    )
    assert cash["payout_cents"] == 6000 - 3540  # the points' value, less the commission the shop owes
    [row] = await rows(ShopEarning, ShopEarning.booking_id == "bk-cash")
    assert row.platform_discount_cents == 6000


@pytest.mark.asyncio
async def test_a_friends_code_rewards_both_once_after_the_first_booking(http):
    code = (await mine(http, "alice"))["referral_code"]
    assert (await http.post("/api/v1/loyalty/referral", json={"code": code}, headers=auth("alice"))).status_code == 422
    assert (
        await http.post("/api/v1/loyalty/referral", json={"code": "NOPE1234"}, headers=auth("bob"))
    ).status_code == 404
    used = await http.post("/api/v1/loyalty/referral", json={"code": code.lower()}, headers=auth("bob"))
    assert used.status_code == 201, used.text
    assert (await http.post("/api/v1/loyalty/referral", json={"code": code}, headers=auth("bob"))).status_code == 409
    assert (await mine(http, "alice"))["friends_pending"] == 1
    assert (await mine(http, "bob"))["referred_by_friend"] is True

    await completed(http, "bk-bob-1", 10000, customer="bob")
    await completed(http, "bk-bob-2", 10000, customer="bob")  # a second booking: no second bonus
    assert (await mine(http, "bob"))["points"] == 100 + 2 + 2
    alice = await mine(http, "alice")
    assert (alice["points"], alice["friends_rewarded"], alice["friends_pending"]) == (100, 1, 0)

    # Codes are for new customers.
    await completed(http, "bk-carol", 10000, customer="carol")
    late = await http.post("/api/v1/loyalty/referral", json={"code": code}, headers=auth("carol"))
    assert late.status_code == 409


@pytest.mark.asyncio
async def test_points_earned_on_a_booking_refunded_in_full_are_taken_back(http):
    pid = await paid_by_razorpay(http, "key-loyal-2", "bk-1")
    await completed(http, "bk-1", 49900)
    assert (await mine(http))["points"] == 9
    await http.post(f"/api/v1/payments/{pid}/refund", json={"amount_cents": 49900, "reason": "Dispute"}, headers=ADMIN)
    me = await mine(http)
    assert me["points"] == 0
    assert [h["kind"] for h in me["history"]][:1] == ["CLAWBACK"]
