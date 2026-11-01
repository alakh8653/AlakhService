"""Profile photos: stored on disk, served back, replaced and removed with the account."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.user  # noqa: F401
from app.config import settings
from app.core import storage as storage_module
from app.database import Base, get_db
from app.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def auth(sub: str) -> dict:
    token = jwt.encode({"sub": sub, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


ME = auth("user-1")


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module.settings, "AVATAR_STORAGE_DIR", str(tmp_path))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def upload(client, data: bytes, content_type: str, headers=ME):
    return await client.post("/api/v1/users/me/avatar", files={"file": ("photo", data, content_type)}, headers=headers)


@pytest.mark.asyncio
async def test_an_uploaded_photo_is_stored_and_served_back(client, tmp_path):
    response = await upload(client, PNG, "image/png")
    assert response.status_code == 200
    url = response.json()["avatar_url"]
    assert url.startswith("/api/v1/users/avatars/") and url.endswith(".png")

    served = await client.get(url)
    assert served.status_code == 200
    assert served.content == PNG
    assert served.headers["content-type"] == "image/png"
    assert "immutable" in served.headers["cache-control"]

    profile = (await client.get("/api/v1/users/me/profile", headers=ME)).json()
    assert profile["avatar_url"] == url
    assert len(list(tmp_path.rglob("*.png"))) == 1


@pytest.mark.asyncio
async def test_a_new_photo_replaces_the_old_file(client, tmp_path):
    first = (await upload(client, PNG, "image/png")).json()["avatar_url"]
    second = (await upload(client, JPEG, "image/jpeg")).json()["avatar_url"]
    assert first != second
    assert (await client.get(first)).status_code == 404
    assert (await client.get(second)).status_code == 200
    assert [p.suffix for p in tmp_path.rglob("*.*")] == [".jpg"]


@pytest.mark.asyncio
async def test_files_that_are_not_what_they_claim_are_refused(client, tmp_path):
    assert (await upload(client, b"<script>alert(1)</script>", "image/png")).status_code == 400
    assert (await upload(client, PNG, "image/gif")).status_code == 400
    assert (await upload(client, b"RIFF\x00\x00\x00\x00AVI ", "image/webp")).status_code == 400
    assert list(tmp_path.rglob("*.*")) == []


@pytest.mark.asyncio
async def test_photos_over_the_size_limit_are_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_AVATAR_SIZE_MB", 1)
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (1024 * 1024)
    assert (await upload(client, big, "image/png")).status_code == 400


@pytest.mark.asyncio
async def test_serving_cannot_reach_outside_the_storage_directory(client):
    assert (await client.get("/api/v1/users/avatars/..%2F..%2Fetc/passwd.png")).status_code == 404
    assert (await client.get("/api/v1/users/avatars/abc/file.txt")).status_code == 404
    assert (await client.get("/api/v1/users/avatars/abc/missing.png")).status_code == 404
    with pytest.raises(ValueError):
        storage_module.get_storage().path_of("../../etc/passwd")


@pytest.mark.asyncio
async def test_deleting_the_account_removes_the_photos(client, tmp_path):
    url = (await upload(client, PNG, "image/png")).json()["avatar_url"]
    other = (await upload(client, PNG, "image/png", headers=auth("user-2"))).json()["avatar_url"]

    assert (await client.delete("/api/v1/users/me/account", headers=ME)).status_code == 200
    assert (await client.get(url)).status_code == 404
    # Someone else's photo is untouched.
    assert (await client.get(other)).status_code == 200


@pytest.mark.asyncio
async def test_uploads_can_be_turned_off(client, monkeypatch):
    monkeypatch.setattr(storage_module.settings, "AVATAR_STORAGE_DIR", "")
    assert (await upload(client, PNG, "image/png")).status_code == 503
