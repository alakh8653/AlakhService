import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_consent_calls(monkeypatch):
    """Sign-ups record consent with compliance_service after the response; tests never reach it."""

    async def skip(*args, **kwargs):
        return None

    monkeypatch.setattr("app.routers.auth.record_terms_consent", skip)
