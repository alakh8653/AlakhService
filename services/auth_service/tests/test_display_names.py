"""Other services learn only a display name ("Ravi K.") for a user, and a phone only for a masked call."""

import pytest

from app.config import settings
from app.routers.users import display_name
from tests.test_accounts_api import KEY, bearer, client  # noqa: F401  (the fixture)

INTERNAL = {"X-Internal-Key": KEY}


@pytest.mark.parametrize(
    "full_name,expected",
    [
        ("Ravi Sharma", "Ravi S."),
        ("ravi kumar sharma", "Ravi S."),
        ("Asha", "Asha"),
        ("  Priya   D'Souza ", "Priya D."),
        ("Jean-Luc Picard", "Jean-Luc P."),
        ("", "Customer"),
        (None, "Customer"),
        ("Ravi 9876543210", "Customer"),
        ("ravi@example.com", "Customer"),
        ("Call me 98765", "Customer"),
        ("राहुल शर्मा", "राहुल श."),
    ],
)
def test_display_name_is_first_name_and_last_initial(full_name, expected):
    assert display_name(full_name) == expected


def test_an_inactive_account_reads_customer():
    assert display_name("Ravi Sharma", is_active=False) == "Customer"


async def _ids(client):  # noqa: F811
    users = (await client.get("/api/v1/auth/users", headers=bearer("ops", "admin"))).json()
    return {u["full_name"]: u["id"] for u in users}


@pytest.mark.asyncio
async def test_display_names_return_only_names(client):  # noqa: F811
    ids = await _ids(client)
    resp = await client.post(
        "/internal/users/display-names",
        json={"user_ids": [ids["Ravi Kumar"], ids["Asha Rao"], "nobody"]},
        headers=INTERNAL,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"names": {ids["Ravi Kumar"]: "Ravi K.", ids["Asha Rao"]: "Asha R.", "nobody": "Customer"}}
    assert "example.com" not in resp.text and "Kumar" not in resp.text


@pytest.mark.asyncio
async def test_internal_contact_routes_need_the_key(client, monkeypatch):  # noqa: F811
    ids = await _ids(client)
    url = "/internal/users/display-names"
    assert (await client.post(url, json={"user_ids": ["x"]})).status_code == 401
    assert (await client.post(url, json={"user_ids": ["x"]}, headers=bearer("ops", "admin"))).status_code == 401
    assert (await client.post("/api/v1" + url, json={"user_ids": ["x"]}, headers=INTERNAL)).status_code == 404
    contact = f"/internal/users/{ids['Ravi Kumar']}/call-contact"
    assert (await client.get(contact, headers=bearer(ids["Ravi Kumar"]))).status_code == 401
    assert (await client.get(contact, headers=INTERNAL)).json() == {"phone": None}
    assert (await client.get("/internal/users/nobody/call-contact", headers=INTERNAL)).status_code == 404
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")
    assert (await client.post(url, json={"user_ids": ["x"]}, headers={"X-Internal-Key": ""})).status_code == 503


@pytest.mark.asyncio
async def test_display_names_take_at_most_200_ids(client):  # noqa: F811
    resp = await client.post(
        "/internal/users/display-names", json={"user_ids": [str(i) for i in range(201)]}, headers=INTERNAL
    )
    assert resp.status_code == 422
