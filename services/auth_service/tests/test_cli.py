"""The operator command that grants and revokes admin access (python -m app.cli)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.cli import set_role
from app.core.security import hash_password
from app.database import Base
from app.models.user import User


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                User(email="ravi@example.com", hashed_password=hash_password("Passw0rd!"), full_name="Ravi Kumar"),
                User(phone="+919876543210", hashed_password=hash_password("Passw0rd!"), full_name="Asha Rao"),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_make_admin_by_email_ignores_case(db):
    user = await set_role(db, "RAVI@Example.com", "admin")
    assert user.email == "ravi@example.com"
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_make_admin_by_phone_then_revoke(db):
    assert (await set_role(db, "+919876543210", "admin")).role == "admin"
    assert (await set_role(db, "+919876543210", "user")).role == "user"


@pytest.mark.asyncio
async def test_unknown_account_is_refused(db):
    with pytest.raises(LookupError):
        await set_role(db, "nobody@example.com", "admin")
