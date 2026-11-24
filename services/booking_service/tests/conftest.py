"""Tests change a line and look at it straight away, under a frozen clock."""

import pytest

from app.core import live_queue


@pytest.fixture(autouse=True)
def no_shared_line(monkeypatch):
    monkeypatch.setattr(live_queue, "LINE_CACHE_SECONDS", 0)
    live_queue._line_cache.clear()
