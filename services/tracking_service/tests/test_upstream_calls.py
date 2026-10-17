"""Ids from the client are quoted into booking_service URLs, so they cannot reach another endpoint."""

import functools

import httpx
import pytest

from app.dependencies import Caller, may_track


@pytest.mark.anyio
async def test_a_provider_id_with_a_path_in_it_stays_one_path_segment(monkeypatch):
    seen = []

    def booking_service(request):
        seen.append(request.url.raw_path)
        return httpx.Response(404)

    monkeypatch.setattr(
        httpx, "AsyncClient", functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(booking_service))
    )
    assert await may_track("../../admin?x=1", Caller("carol", "user", "tok")) is False
    assert seen == [b"/api/v1/bookings/tracking/..%2F..%2Fadmin%3Fx%3D1"]
