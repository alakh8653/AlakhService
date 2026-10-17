"""Ids from the client are quoted into catalogue and shop URLs, so they cannot reach another endpoint."""

import functools

import httpx
import pytest

from app.dependencies import fetch_service_owner


@pytest.mark.anyio
async def test_a_service_id_with_a_path_in_it_stays_one_path_segment(monkeypatch):
    seen = []

    def upstream(request):
        seen.append(request.url.raw_path)
        if request.url.path.startswith("/api/v1/services/"):
            return httpx.Response(200, json={"shop_id": "../../users/me"})
        return httpx.Response(200, json={"owner_id": "alice"})

    monkeypatch.setattr(
        httpx, "AsyncClient", functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(upstream))
    )
    assert await fetch_service_owner("../shops/alices-shop") == "alice"
    assert seen == [b"/api/v1/services/..%2Fshops%2Falices-shop", b"/api/v1/shops/..%2F..%2Fusers%2Fme"]
