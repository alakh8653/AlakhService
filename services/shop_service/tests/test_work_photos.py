"""Work photos and profile details: what customers see before booking, with nothing private left in them."""

import io

import pytest
from PIL import Image

from app.config import settings
from app.core.photos import NotAPhoto, clean_photo
from app.core.storage import LocalDocumentStorage, get_storage
from app.main import app
from tests import test_reviews_api
from tests.test_reviews_api import ADMIN, auth, make_shop

client = test_reviews_api.client
OWNER = auth("owner-1")


def photo(size=(40, 30), format="JPEG", exif=None) -> bytes:
    out = io.BytesIO()
    image = Image.new("RGB", size, (200, 30, 30))
    image.save(out, format, **({"exif": exif} if exif else {}))
    return out.getvalue()


def with_location() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (12.0, 58.0, 0.0)
    return photo(exif=exif.tobytes())


@pytest.fixture(autouse=True)
def storage(tmp_path):
    app.dependency_overrides[get_storage] = lambda: LocalDocumentStorage(str(tmp_path))
    yield


async def upload(client, shop_id, data=None, headers=OWNER, caption=None):  # noqa: F811
    return await client.post(
        f"/api/v1/shops/{shop_id}/photos",
        content=data if data is not None else photo(),
        headers={**headers, "Content-Type": "image/jpeg"},
        params={"caption": caption} if caption else None,
    )


def test_location_and_camera_details_are_removed():
    original = with_location()
    assert b"SecretCameraMaker" in original
    assert Image.open(io.BytesIO(original)).getexif().get_ifd(0x8825)
    cleaned = clean_photo(original)
    assert b"SecretCameraMaker" not in cleaned
    image = Image.open(io.BytesIO(cleaned))
    assert image.format == "JPEG"
    assert not image.getexif()


def test_big_photos_are_made_smaller_and_any_format_becomes_a_jpeg():
    assert max(Image.open(io.BytesIO(clean_photo(photo(size=(4000, 3000))))).size) == 1600
    assert Image.open(io.BytesIO(clean_photo(photo(format="PNG")))).format == "JPEG"


@pytest.mark.parametrize(
    "data", [b"", b"<script>alert(1)</script>", b"%PDF-1.4 not a photo", b"\xff\xd8\xff not really a jpeg"]
)
def test_what_is_not_a_photo_is_refused(data):
    with pytest.raises(NotAPhoto):
        clean_photo(data)


@pytest.mark.asyncio
async def test_an_owner_adds_a_photo_and_customers_can_see_it(client):
    shop_id = await make_shop(client)
    resp = await upload(client, shop_id, with_location(), caption="New wiring")
    assert resp.status_code == 201
    body = resp.json()
    assert body["caption"] == "New wiring"
    listed = (await client.get(f"/api/v1/shops/{shop_id}/photos")).json()
    assert [p["id"] for p in listed] == [body["id"]]
    file = await client.get(body["url"])
    assert file.status_code == 200
    assert file.headers["content-type"] == "image/jpeg"
    assert b"SecretCameraMaker" not in file.content
    assert file.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_only_the_owner_or_an_admin_adds_or_removes(client):
    shop_id = await make_shop(client)
    assert (await upload(client, shop_id, headers=auth("someone-else"))).status_code == 403
    added = (await upload(client, shop_id)).json()
    url = f"/api/v1/shops/{shop_id}/photos/{added['id']}"
    assert (await client.delete(url, headers=auth("someone-else"))).status_code == 403
    assert (await client.delete(url, headers=ADMIN)).status_code == 204
    assert (await client.get(added["url"])).status_code == 404


@pytest.mark.asyncio
async def test_junk_and_too_many_are_refused(client, monkeypatch):
    shop_id = await make_shop(client)
    assert (await upload(client, shop_id, b"<script>")).status_code == 422
    monkeypatch.setattr(settings, "MAX_WORK_PHOTOS", 1)
    assert (await upload(client, shop_id)).status_code == 201
    resp = await upload(client, shop_id)
    assert resp.status_code == 409 and "remove one" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a_hidden_shops_photos_are_not_listed_for_customers(client):
    shop_id = await make_shop(client)
    await upload(client, shop_id)
    await client.put(f"/api/v1/shops/{shop_id}", json={"is_active": False}, headers=OWNER)
    assert (await client.get(f"/api/v1/shops/{shop_id}/photos")).status_code == 404
    assert len((await client.get(f"/api/v1/shops/{shop_id}/photos", headers=OWNER)).json()) == 1


@pytest.mark.asyncio
async def test_a_phone_number_in_a_caption_is_hidden_from_customers(client):
    shop_id = await make_shop(client)
    await upload(client, shop_id, caption="Call 9876543210")
    assert "9876543210" not in (await client.get(f"/api/v1/shops/{shop_id}/photos")).json()[0]["caption"]
    assert "9876543210" in (await client.get(f"/api/v1/shops/{shop_id}/photos", headers=OWNER)).json()[0]["caption"]


@pytest.mark.asyncio
async def test_experience_and_languages_are_saved_and_public_and_contact_details_hidden(client):
    shop_id = await make_shop(client)
    url = f"/api/v1/shops/{shop_id}"
    body = {
        "description": "Ten years of AC work. Call 9876543210",
        "years_experience": 10,
        "languages": ["Hindi", "Tamil"],
    }
    assert (await client.put(url, json=body, headers=OWNER)).status_code == 200
    public = (await client.get(url)).json()
    assert (public["years_experience"], public["languages"]) == (10, ["Hindi", "Tamil"])
    assert "9876543210" not in public["description"] and "Ten years" in public["description"]
    # The owner still reads what they wrote.
    assert "9876543210" in (await client.get(url, headers=OWNER)).json()["description"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        {"years_experience": -1},
        {"years_experience": 71},
        {"languages": ["x" * 31]},
        {"languages": ["Hindi"] * 13},
        {"description": "x" * 1001},
    ],
)
async def test_nonsense_is_refused(client, bad):
    shop_id = await make_shop(client)
    assert (await client.put(f"/api/v1/shops/{shop_id}", json=bad, headers=OWNER)).status_code == 422
