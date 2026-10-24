import os

# The background worker never runs under tests; they call its steps directly.
os.environ.setdefault("REMINDERS_ENABLED", "false")

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
