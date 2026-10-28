"""Deleting an account erases the person's data in the other services, as them, before the sign-in goes."""

import httpx
import pytest
from fastapi import HTTPException

from app.routers.users import erase_profile


def recording(status_by_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.host, request.url.path, request.headers["authorization"]))
        return httpx.Response(status_by_path.get(request.url.path, 200))

    return calls, httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_saved_shops_and_the_profile_are_erased_as_the_person():
    calls, transport = recording({"/api/v1/shops/favorites": 204})
    await erase_profile("tok", transport=transport)
    assert calls == [
        ("DELETE", "shop_service", "/api/v1/shops/favorites", "Bearer tok"),
        ("DELETE", "user_service", "/api/v1/users/me/account", "Bearer tok"),
    ]


@pytest.mark.asyncio
async def test_a_failure_stops_the_deletion_so_it_can_be_retried():
    calls, transport = recording({"/api/v1/shops/favorites": 500})
    with pytest.raises(HTTPException) as e:
        await erase_profile("tok", transport=transport)
    assert e.value.status_code == 503
    assert [c[2] for c in calls] == ["/api/v1/shops/favorites"]  # the profile is left for the retry
