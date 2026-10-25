"""Ids from the client are quoted into booking_service URLs, so they cannot reach another endpoint."""

import functools

import httpx
import pytest
from fastapi import HTTPException

from app.dependencies import Caller, assign_in_booking_service


@pytest.mark.anyio
async def test_a_booking_id_with_a_path_in_it_stays_one_path_segment(monkeypatch):
    seen = []

    def booking_service(request):
        seen.append(request.url.raw_path)
        return httpx.Response(404)

    monkeypatch.setattr(
        httpx, "AsyncClient", functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(booking_service))
    )
    with pytest.raises(HTTPException) as err:
        await assign_in_booking_service("../other-booking", "prov-1", Caller("ops", "admin", "tok"))
    assert err.value.status_code == 404
    assert seen == [b"/api/v1/bookings/..%2Fother-booking/assign"]
