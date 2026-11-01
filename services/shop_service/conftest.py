import os

import pytest

# No background listing resync under tests (it would call service_catalog).
os.environ.setdefault("LISTING_RESYNC_SECONDS", "0")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
