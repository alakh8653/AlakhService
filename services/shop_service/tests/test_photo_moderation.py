"""Customers report bad work photos; admins keep, hide or remove them, and the owner is told."""

import pytest

from app.core.reporting import get_reporter
from app.core.storage import LocalDocumentStorage, get_storage
from app.main import app
from tests import test_reviews_api
from tests.test_kyc_api import FakeReporter
from tests.test_reviews_api import ADMIN, auth, make_shop
from tests.test_work_photos import photo, upload

client = test_reviews_api.client
OWNER = auth("owner-1")
REASON = {"reason": "Shows a customer's ID card"}
QUEUE = "/api/v1/admin/work-photos"


@pytest.fixture(autouse=True)
def storage(tmp_path):
    app.dependency_overrides[get_storage] = lambda: LocalDocumentStorage(str(tmp_path))


@pytest.fixture
def reporter():
    fake = FakeReporter()
    app.dependency_overrides[get_reporter] = lambda: fake
    return fake


async def added(client):  # noqa: F811
    shop_id = await make_shop(client)
    body = (await upload(client, shop_id, photo())).json()
    return shop_id, body


def report_url(shop_id, photo_id):
    return f"/api/v1/shops/{shop_id}/photos/{photo_id}/report"


@pytest.mark.asyncio
async def test_a_report_reaches_the_admin_and_the_photo_stays_up_at_first(client, reporter):
    shop_id, body = await added(client)
    resp = await client.post(report_url(shop_id, body["id"]), json=REASON, headers=auth("c1"))
    assert resp.status_code == 202
    assert (await client.get(f"/api/v1/shops/{shop_id}/photos")).json()[0]["id"] == body["id"]
    assert (await client.get(body["url"])).status_code == 200

    queue = (await client.get(QUEUE, headers=ADMIN)).json()
    assert queue["total"] == 1
    item = queue["items"][0]
    assert (item["report_count"], item["report_reasons"], item["is_hidden"]) == (1, [REASON["reason"]], False)
    assert item["shop_name"]


@pytest.mark.asyncio
async def test_reporting_needs_a_sign_in_and_one_person_counts_once(client, reporter):
    shop_id, body = await added(client)
    url = report_url(shop_id, body["id"])
    assert (await client.post(url, json=REASON)).status_code in (401, 403)
    assert (await client.post(url, json=REASON, headers=auth("c1"))).status_code == 202
    assert (await client.post(url, json=REASON, headers=auth("c1"))).status_code == 200
    assert (await client.get(QUEUE, headers=ADMIN)).json()["items"][0]["report_count"] == 1


@pytest.mark.asyncio
async def test_three_different_people_hide_it_until_an_admin_looks_and_the_owner_is_told(client, reporter):
    shop_id, body = await added(client)
    for who in ("c1", "c2", "c3"):
        assert (await client.post(report_url(shop_id, body["id"]), json=REASON, headers=auth(who))).status_code == 202
    assert (await client.get(f"/api/v1/shops/{shop_id}/photos")).json() == []
    assert (await client.get(body["url"])).status_code == 404
    assert reporter.notifications[-1][:2] == ("shop.photo_hidden", "owner-1")
    # The owner still sees it, marked, and so does the admin who has to judge it.
    mine = (await client.get(f"/api/v1/shops/{shop_id}/photos", headers=OWNER)).json()[0]
    assert mine["is_hidden"] is True
    assert (await client.get(body["url"], headers=ADMIN)).status_code == 200
    assert (await client.get(body["url"], headers=OWNER)).status_code == 200
    assert (await client.get(body["url"], headers=auth("c1"))).status_code == 404
    # Nothing more to report on a hidden photo.
    assert (await client.post(report_url(shop_id, body["id"]), json=REASON, headers=auth("c4"))).status_code == 404


@pytest.mark.asyncio
async def test_keeping_a_photo_clears_its_reports_and_it_can_be_reported_again(client, reporter):
    shop_id, body = await added(client)
    for who in ("c1", "c2", "c3"):
        await client.post(report_url(shop_id, body["id"]), json=REASON, headers=auth(who))
    resp = await client.put(f"{QUEUE}/{body['id']}", json={"hidden": False}, headers=ADMIN)
    assert resp.status_code == 200
    assert (resp.json()["is_hidden"], resp.json()["report_count"]) == (False, 0)
    assert (await client.get(QUEUE, headers=ADMIN)).json()["total"] == 0
    assert (await client.get(body["url"])).status_code == 200
    assert reporter.audits[-1][1] == "shop.photo_keep"
    assert (await client.post(report_url(shop_id, body["id"]), json=REASON, headers=auth("c1"))).status_code == 202


@pytest.mark.asyncio
async def test_an_admin_hides_one_and_the_owner_is_told(client, reporter):
    shop_id, body = await added(client)
    resp = await client.put(f"{QUEUE}/{body['id']}", json={"hidden": True}, headers=ADMIN)
    assert (resp.status_code, resp.json()["is_hidden"]) == (200, True)
    assert reporter.notifications[-1][:2] == ("shop.photo_hidden", "owner-1")
    assert reporter.audits[-1][1] == "shop.photo_hide"
    assert (await client.get(f"{QUEUE}?status=hidden", headers=ADMIN)).json()["total"] == 1


@pytest.mark.asyncio
async def test_an_admin_removes_one_for_good(client, reporter):
    shop_id, body = await added(client)
    await client.post(report_url(shop_id, body["id"]), json=REASON, headers=auth("c1"))
    assert (await client.delete(f"{QUEUE}/{body['id']}", headers=ADMIN)).status_code == 204
    assert (await client.get(body["url"], headers=ADMIN)).status_code == 404
    assert (await client.get(f"{QUEUE}?status=all", headers=ADMIN)).json()["total"] == 0
    assert reporter.notifications[-1][:2] == ("shop.photo_removed", "owner-1")
    assert reporter.audits[-1][1] == "shop.photo_remove"


@pytest.mark.asyncio
async def test_all_shows_every_photo_for_looking_through(client, reporter):
    await added(client)
    assert (await client.get(QUEUE, headers=ADMIN)).json()["total"] == 0
    assert (await client.get(f"{QUEUE}?status=all", headers=ADMIN)).json()["total"] == 1


@pytest.mark.asyncio
async def test_only_admins_can_use_the_queue(client, reporter):
    _, body = await added(client)
    assert (await client.get(QUEUE, headers=OWNER)).status_code == 403
    assert (await client.put(f"{QUEUE}/{body['id']}", json={"hidden": False}, headers=OWNER)).status_code == 403
    assert (await client.delete(f"{QUEUE}/{body['id']}", headers=OWNER)).status_code == 403
