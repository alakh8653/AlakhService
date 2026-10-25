"""Shop onboarding: review status and who sees what, KYC documents, payout details and admin review."""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.shop  # noqa: F401
from app.config import settings
from app.core.kyc import gstin_check_character, mask_account_number, normalise_gstin
from app.core.reporting import get_reporter
from app.core.storage import LocalDocumentStorage, get_storage
from app.database import Base, get_db
from app.main import app
from tests.test_staff_api import ADMIN, OTHER, OWNER, auth

GSTIN = "27AAPFU0939F1ZV"
PDF = b"%PDF-1.7\n" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
INTERNAL_KEY = "k" * 40


class FakeReporter:
    def __init__(self):
        self.audits = []
        self.notifications = []
        self.listings = []

    async def audit(self, admin_id, action, shop_id, origin, old_values=None, new_values=None):
        self.audits.append((admin_id, action, shop_id, old_values, new_values))

    async def notify_owner(self, event, owner_id, data):
        self.notifications.append((event, owner_id, data))

    async def sync_listing(self, shop_id, listed):
        self.listings.append((shop_id, listed))


@pytest.fixture
def reporter():
    return FakeReporter()


@pytest_asyncio.fixture
async def client(tmp_path, reporter, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: LocalDocumentStorage(str(tmp_path / "docs"))
    app.dependency_overrides[get_reporter] = lambda: reporter
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def new_shop(client, owner="owner-1", **extra):
    resp = await client.post(
        "/api/v1/shops",
        json={"owner_id": owner, "name": "Glow Salon", "category": "salon", "city": "Pune", **extra},
        headers=auth(owner),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_link(client, shop_id, doc_type="PAN", headers=OWNER):
    return await client.post(
        f"/api/v1/shops/{shop_id}/documents",
        json={"type": doc_type, "url": "https://files.example.com/pan.pdf"},
        headers=headers,
    )


async def upload(client, shop_id, data=PDF, content_type="application/pdf", doc_type="PAN", headers=OWNER):
    return await client.post(
        f"/api/v1/shops/{shop_id}/documents/upload",
        params={"type": doc_type, "file_name": "../../pan card.pdf"},
        content=data,
        headers={**headers, "Content-Type": content_type},
    )


async def ready_for_review(client, **extra):
    shop = await new_shop(client, legal_name="Glow Salon Pvt Ltd", **extra)
    assert (await add_link(client, shop["id"])).status_code == 201
    submitted = await client.post(f"/api/v1/shops/{shop['id']}/submit-for-review", headers=OWNER)
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


# Identifiers


def test_gstin_format_and_check_character():
    assert normalise_gstin(" 27aapfu0939f1zv ") == GSTIN
    assert normalise_gstin("") is None
    assert gstin_check_character("29AAGCB7383J1Z") == "4"
    for bad in ("27AAPFU0939F1Z", "27AAPFU0939F1ZW", "99AAPFU0939F1ZV", "27AAPFU0939F1AV"):
        with pytest.raises(ValueError):
            normalise_gstin(bad)


def test_account_numbers_are_masked_to_the_last_four_digits():
    assert mask_account_number("123456789012") == "XXXXXXXX9012"
    assert mask_account_number(None) is None


def test_migrations_have_a_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = Config(os.path.join(root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(root, "migrations"))
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1


# Status and visibility


@pytest.mark.asyncio
async def test_new_shops_are_hidden_until_approved_but_their_owner_and_admins_see_them(client):
    shop = await new_shop(client, legal_name="Glow Salon Pvt Ltd", gstin=GSTIN)
    assert (shop["verification_status"], shop["is_verified"]) == ("PENDING_REVIEW", False)
    assert shop["gstin"] == GSTIN

    for headers in ({}, OTHER):
        assert (await client.get(f"/api/v1/shops/{shop['id']}", headers=headers)).status_code == 404
        assert (await client.get("/api/v1/shops", headers=headers)).json() == []
        assert (await client.get("/api/v1/shops/search", params={"city": "Pune"}, headers=headers)).json() == []
    for headers in (OWNER, ADMIN):
        assert (await client.get(f"/api/v1/shops/{shop['id']}", headers=headers)).status_code == 200
    mine = (await client.get("/api/v1/shops", params={"owner_id": "owner-1"}, headers=OWNER)).json()
    assert [s["id"] for s in mine] == [shop["id"]]
    # Platform services finding the owner of a pending shop send the internal key.
    internal = await client.get(f"/api/v1/shops/{shop['id']}", headers={"X-Internal-Key": INTERNAL_KEY})
    assert internal.status_code == 200 and internal.json()["owner_id"] == "owner-1"
    assert (await client.get(f"/api/v1/shops/{shop['id']}", headers={"X-Internal-Key": "wrong"})).status_code == 404

    await client.post(f"/api/v1/admin/shops/{shop['id']}/approve", headers=ADMIN)
    public = await client.get(f"/api/v1/shops/{shop['id']}")
    assert public.status_code == 200
    assert (public.json()["verification_status"], public.json()["is_verified"]) == ("APPROVED", True)
    # The KYC details stay with the owner and admins.
    assert (public.json()["gstin"], public.json()["legal_name"]) == (None, None)
    assert [s["id"] for s in (await client.get("/api/v1/shops/search", params={"city": "Pune"})).json()] == [shop["id"]]

    # A closed shop leaves the public pages too.
    await client.put(f"/api/v1/shops/{shop['id']}", json={"is_active": False}, headers=OWNER)
    assert (await client.get(f"/api/v1/shops/{shop['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/shops/{shop['id']}", headers=OWNER)).status_code == 200


@pytest.mark.asyncio
async def test_gstin_is_validated_on_create_and_update(client):
    bad = await client.post(
        "/api/v1/shops",
        json={"owner_id": "owner-1", "name": "X", "category": "salon", "gstin": "27AAPFU0939F1ZW"},
        headers=OWNER,
    )
    assert bad.status_code == 422
    shop = await new_shop(client)
    url = f"/api/v1/shops/{shop['id']}"
    assert (await client.put(url, json={"gstin": "NOT-A-GSTIN"}, headers=OWNER)).status_code == 422
    updated = await client.put(url, json={"gstin": GSTIN.lower(), "legal_name": "  Glow Pvt Ltd "}, headers=OWNER)
    assert (updated.json()["gstin"], updated.json()["legal_name"]) == (GSTIN, "Glow Pvt Ltd")


@pytest.mark.asyncio
async def test_owners_cannot_set_their_own_status(client):
    shop = await new_shop(client)
    url = f"/api/v1/shops/{shop['id']}"
    await client.put(url, json={"verification_status": "APPROVED", "is_verified": True}, headers=OWNER)
    view = (await client.get(url, headers=OWNER)).json()
    assert (view["verification_status"], view["is_verified"]) == ("PENDING_REVIEW", False)
    assert (await client.post(f"/api/v1/admin/shops/{shop['id']}/approve", headers=OWNER)).status_code == 403


@pytest.mark.asyncio
async def test_verified_legal_details_are_locked_for_the_owner(client):
    shop = await ready_for_review(client, gstin=None)
    await client.post(f"/api/v1/admin/shops/{shop['id']}/approve", headers=ADMIN)
    url = f"/api/v1/shops/{shop['id']}"
    assert (await client.put(url, json={"legal_name": "Someone Else Ltd"}, headers=OWNER)).status_code == 409
    # Other details, and the same value again, are fine; an admin can correct them.
    assert (
        await client.put(url, json={"legal_name": "Glow Salon Pvt Ltd", "city": "Mumbai"}, headers=OWNER)
    ).status_code == 200
    assert (await client.put(url, json={"legal_name": "Glow Salon LLP"}, headers=ADMIN)).status_code == 200


# Submitting and reviewing


@pytest.mark.asyncio
async def test_submitting_needs_a_legal_name_and_pan_and_a_gst_certificate_when_gstin_is_given(client):
    shop = await new_shop(client, gstin=GSTIN)
    url = f"/api/v1/shops/{shop['id']}/submit-for-review"
    missing = await client.post(url, headers=OWNER)
    assert missing.status_code == 409
    assert "legal name" in missing.json()["detail"] and "PAN" in missing.json()["detail"]
    assert "GST certificate" in missing.json()["detail"]

    await client.put(f"/api/v1/shops/{shop['id']}", json={"legal_name": "Glow Salon Pvt Ltd"}, headers=OWNER)
    await add_link(client, shop["id"], "PAN")
    assert (await client.post(url, headers=OWNER)).status_code == 409
    await add_link(client, shop["id"], "GST")
    assert (await client.post(url, headers=OTHER)).status_code == 403
    done = await client.post(url, headers=OWNER)
    assert done.status_code == 200
    assert done.json()["submitted_at"] is not None


@pytest.mark.asyncio
async def test_review_queue_approve_and_reject(client, reporter):
    waiting = await new_shop(client, owner="owner-9")  # never submitted: not in the queue yet
    first = await ready_for_review(client)
    assert (await client.get("/api/v1/admin/shops/review-queue", headers=OWNER)).status_code == 403

    queue = (await client.get("/api/v1/admin/shops/review-queue", headers=ADMIN)).json()
    assert [s["id"] for s in queue] == [first["id"]]
    assert queue[0]["documents"][0]["type"] == "PAN"
    assert queue[0]["legal_name"] == "Glow Salon Pvt Ltd"
    assert queue[0]["has_payout_details"] is False

    reject_url = f"/api/v1/admin/shops/{first['id']}/reject"
    assert (await client.post(reject_url, json={"reason": "no"}, headers=ADMIN)).status_code == 422
    assert (await client.post(reject_url, json={}, headers=ADMIN)).status_code == 422
    rejected = await client.post(reject_url, json={"reason": "  PAN photo is blurred  "}, headers=ADMIN)
    assert rejected.status_code == 200
    assert (rejected.json()["verification_status"], rejected.json()["rejection_reason"]) == (
        "REJECTED",
        "PAN photo is blurred",
    )
    assert (await client.get("/api/v1/admin/shops/review-queue", headers=ADMIN)).json() == []
    # The owner sees why; customers still cannot find it.
    mine = (await client.get(f"/api/v1/shops/{first['id']}", headers=OWNER)).json()
    assert mine["rejection_reason"] == "PAN photo is blurred"
    assert (await client.get(f"/api/v1/shops/{first['id']}")).status_code == 404

    # Resubmitting puts it back in the queue and clears the old reason.
    again = await client.post(f"/api/v1/shops/{first['id']}/submit-for-review", headers=OWNER)
    assert (again.json()["verification_status"], again.json()["rejection_reason"]) == ("PENDING_REVIEW", None)

    approved = await client.post(f"/api/v1/admin/shops/{first['id']}/approve", headers=ADMIN)
    assert approved.status_code == 200
    assert (approved.json()["verification_status"], approved.json()["is_verified"]) == ("APPROVED", True)
    assert (await client.post(f"/api/v1/admin/shops/{first['id']}/approve", headers=ADMIN)).status_code == 409
    assert (await client.post(f"/api/v1/shops/{first['id']}/submit-for-review", headers=OWNER)).status_code == 409
    docs = (await client.get(f"/api/v1/shops/{first['id']}/documents", headers=OWNER)).json()
    assert all(d["is_verified"] for d in docs)

    assert [a[1] for a in reporter.audits] == ["shop.reject", "shop.approve"]
    assert reporter.audits[0][4]["rejection_reason"] == "PAN photo is blurred"
    assert [(n[0], n[1]) for n in reporter.notifications] == [
        ("shop.rejected", "owner-1"),
        ("shop.approved", "owner-1"),
    ]
    assert reporter.notifications[0][2]["reason"] == "PAN photo is blurred"
    # service_catalog hides the shop's services until approval, then shows them.
    assert reporter.listings == [(first["id"], False), (first["id"], True)]
    # Switching the approved shop off hides them again.
    assert (
        await client.put(f"/api/v1/shops/{first['id']}", json={"is_active": False}, headers=OWNER)
    ).status_code == 200
    assert reporter.listings[-1] == (first["id"], False)
    assert waiting["id"] not in [s["id"] for s in queue]


@pytest.mark.asyncio
async def test_admins_list_every_shop_by_status(client):
    a = await new_shop(client, owner="owner-1")
    b = await new_shop(client, owner="owner-2")
    await client.post(f"/api/v1/admin/shops/{b['id']}/approve", headers=ADMIN)
    assert (await client.get("/api/v1/admin/shops", headers=OWNER)).status_code == 403
    every = (await client.get("/api/v1/admin/shops", headers=ADMIN)).json()
    assert every["total"] == 2
    pending = (await client.get("/api/v1/admin/shops", params={"status": "PENDING_REVIEW"}, headers=ADMIN)).json()
    assert [s["id"] for s in pending["items"]] == [a["id"]]
    assert (await client.get("/api/v1/admin/shops", params={"status": "NOPE"}, headers=ADMIN)).status_code == 422
    one = (await client.get(f"/api/v1/admin/shops/{a['id']}", headers=ADMIN)).json()
    assert one["documents"] == []
    assert (await client.get("/api/v1/admin/shops/missing", headers=ADMIN)).status_code == 404


# Documents


@pytest.mark.asyncio
async def test_document_links_must_be_https_and_of_a_known_type(client):
    shop = await new_shop(client)
    url = f"/api/v1/shops/{shop['id']}/documents"
    for body in (
        {"type": "PAN", "url": "http://files.example.com/pan.pdf"},
        {"type": "PAN", "url": "javascript:alert(1)"},
        {"type": "PASSPORT", "url": "https://files.example.com/x.pdf"},
    ):
        assert (await client.post(url, json=body, headers=OWNER)).status_code == 422, body
    assert (await add_link(client, shop["id"], headers=OTHER)).status_code == 403
    assert (await add_link(client, shop["id"], headers={})).status_code == 401
    created = await add_link(client, shop["id"], "UDYAM", headers=ADMIN)
    assert created.status_code == 201 and created.json()["uploaded"] is False
    assert (await client.get(url, headers=OTHER)).status_code == 403
    assert [d["type"] for d in (await client.get(url, headers=OWNER)).json()] == ["UDYAM"]


@pytest.mark.asyncio
async def test_uploads_are_checked_stored_and_only_served_to_the_owner_and_admins(client, monkeypatch):
    shop = await new_shop(client)
    created = await upload(client, shop["id"])
    assert created.status_code == 201, created.text
    doc = created.json()
    assert doc["uploaded"] is True
    assert (doc["content_type"], doc["size_bytes"]) == ("application/pdf", len(PDF))
    assert "/" not in doc["file_name"] and doc["file_name"].endswith("pan card.pdf")
    assert "storage_key" not in doc

    file_url = f"/api/v1/shops/{shop['id']}/documents/{doc['id']}/file"
    assert doc["url"] == file_url
    got = await client.get(file_url, headers=ADMIN)
    assert got.status_code == 200 and got.content == PDF
    assert got.headers["content-type"] == "application/pdf"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert (await client.get(file_url, headers=OTHER)).status_code == 403
    assert (await client.get(file_url, headers={})).status_code == 401

    # The bytes must be what the Content-Type says, and of an allowed kind.
    assert (await upload(client, shop["id"], data=b"<script>alert(1)</script>")).status_code == 415
    assert (await upload(client, shop["id"], data=PNG, content_type="application/pdf")).status_code == 415
    assert (
        await upload(client, shop["id"], data=b"MZ\x90", content_type="application/x-msdownload")
    ).status_code == 415
    assert (await upload(client, shop["id"], data=b"")).status_code == 422
    assert (
        await upload(client, shop["id"], data=PNG, content_type="image/png", doc_type="SHOP_PHOTO")
    ).status_code == 201
    assert (await upload(client, shop["id"], doc_type="SELFIE")).status_code == 422
    assert (await upload(client, shop["id"], headers=OTHER)).status_code == 403

    monkeypatch.setattr(settings, "DOCUMENT_MAX_BYTES", 50)
    assert (await upload(client, shop["id"])).status_code == 413


@pytest.mark.asyncio
async def test_documents_per_shop_are_limited_and_verified_ones_stay(client, monkeypatch):
    shop = await new_shop(client, legal_name="Glow Salon Pvt Ltd")
    monkeypatch.setattr(settings, "MAX_DOCUMENTS_PER_SHOP", 2)
    first = (await upload(client, shop["id"])).json()
    await add_link(client, shop["id"], "GST")
    assert (await add_link(client, shop["id"], "UDYAM")).status_code == 409
    assert (await upload(client, shop["id"])).status_code == 409

    url = f"/api/v1/shops/{shop['id']}/documents/{first['id']}"
    assert (await client.delete(url, headers=OTHER)).status_code == 403
    await client.post(f"/api/v1/shops/{shop['id']}/submit-for-review", headers=OWNER)
    await client.post(f"/api/v1/admin/shops/{shop['id']}/approve", headers=ADMIN)
    assert (await client.delete(url, headers=OWNER)).status_code == 409
    assert (await client.delete(url, headers=ADMIN)).status_code == 204
    assert (await client.get(f"{url}/file", headers=ADMIN)).status_code == 404
    assert (await client.delete(url, headers=ADMIN)).status_code == 404


@pytest.mark.asyncio
async def test_uploads_can_be_turned_off(client):
    shop = await new_shop(client)
    app.dependency_overrides[get_storage] = lambda: LocalDocumentStorage("")
    assert (await upload(client, shop["id"])).status_code == 501
    assert (await add_link(client, shop["id"])).status_code == 201


# Payout details


@pytest.mark.asyncio
async def test_payout_details_are_validated_and_masked(client):
    shop = await new_shop(client)
    url = f"/api/v1/shops/{shop['id']}/payout-details"
    assert (await client.get(url, headers=OWNER)).status_code == 404
    bank = {"method": "BANK", "account_name": "Glow Salon", "account_number": "1234 5678 9012", "ifsc": "hdfc0001234"}
    for bad in (
        {**bank, "ifsc": "HDFC1234567"},
        {**bank, "account_number": "12ab"},
        {**bank, "account_name": ""},
        {"method": "UPI", "upi_id": "not-an-upi"},
        {"method": "UPI"},
        {"method": "CASH"},
    ):
        assert (await client.put(url, json=bad, headers=OWNER)).status_code == 422, bad
    assert (await client.put(url, json=bank, headers=OTHER)).status_code == 403

    saved = await client.put(url, json=bank, headers=OWNER)
    assert saved.status_code == 200
    assert saved.json()["account_number"] == "XXXXXXXX9012"
    assert saved.json()["ifsc"] == "HDFC0001234"
    for headers in (OWNER, ADMIN):
        assert (await client.get(url, headers=headers)).json()["account_number"] == "XXXXXXXX9012"

    internal = f"/internal/shops/{shop['id']}/payout-details"
    assert (await client.get(internal)).status_code == 401
    assert (await client.get(internal, headers={"X-Internal-Key": "wrong"})).status_code == 401
    full = await client.get(internal, headers={"X-Internal-Key": INTERNAL_KEY})
    assert full.json()["account_number"] == "123456789012"

    upi = await client.put(url, json={"method": "UPI", "upi_id": "Glow.Salon@okhdfcbank", "ifsc": "x"}, headers=OWNER)
    assert upi.status_code == 422  # a malformed IFSC is refused even when it would be dropped
    upi = await client.put(url, json={"method": "UPI", "upi_id": "Glow.Salon@okhdfcbank"}, headers=OWNER)
    assert upi.json() | {"updated_at": None} == {
        "shop_id": shop["id"],
        "method": "UPI",
        "account_name": None,
        "account_number": None,
        "ifsc": None,
        "upi_id": "glow.salon@okhdfcbank",
        "updated_at": None,
    }
    queue_item = (await client.get(f"/api/v1/admin/shops/{shop['id']}", headers=ADMIN)).json()
    assert queue_item["has_payout_details"] is True


@pytest.mark.asyncio
async def test_internal_shop_record_has_the_invoice_details_whatever_the_status(client, monkeypatch):
    shop = await new_shop(client, legal_name="Glow Salon Pvt Ltd", legal_address="12 MG Road, Pune", gstin=GSTIN)
    url = f"/internal/shops/{shop['id']}"
    assert (await client.get(url)).status_code == 401
    record = (await client.get(url, headers={"X-Internal-Key": INTERNAL_KEY})).json()
    assert (record["legal_name"], record["legal_address"], record["gstin"]) == (
        "Glow Salon Pvt Ltd",
        "12 MG Road, Pune",
        GSTIN,
    )
    assert record["verification_status"] == "PENDING_REVIEW"
    assert (await client.get("/internal/shops/missing", headers={"X-Internal-Key": INTERNAL_KEY})).status_code == 404
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert (await client.get(url, headers={"X-Internal-Key": ""})).status_code == 503


@pytest.mark.asyncio
async def test_the_catalog_is_told_with_the_internal_key_and_the_id_escaped():
    import httpx

    from app.core.reporting import Reporter

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.raw_path, request.headers.get("x-internal-key"), request.read()))
        return httpx.Response(200, json={})

    reporter = Reporter("http://admin", "http://notify", INTERNAL_KEY, httpx.MockTransport(handler), "http://catalog")
    await reporter.sync_listing("../x", True)
    assert seen == [(b"/internal/shops/%2E%2E%2Fx/listing", INTERNAL_KEY, b'{"listed":true}')]
