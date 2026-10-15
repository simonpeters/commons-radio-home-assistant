"""Tests for the reusable Commons Radio client."""

from __future__ import annotations

from pathlib import Path

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.commons_radio.commonsradio import (
    ApiError,
    Client,
    ForbiddenError,
    RateLimitError,
    UnauthorizedError,
)

from .fixtures import BASE_URL, collection, schedule, station


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, UnauthorizedError),
        (403, ForbiddenError),
        (429, RateLimitError),
        (500, ApiError),
    ],
)
async def test_client_maps_http_errors(
    hass, aioclient_mock, status: int, error_type: type[Exception]
) -> None:
    """Map each important API status to a distinct exception."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", status=status, text="error")
    client = Client(async_get_clientsession(hass), "secret")

    with pytest.raises(error_type):
        await client.get_favorites()


async def test_client_parses_collection(hass, aioclient_mock) -> None:
    """Parse the exact public collection fields."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    client = Client(async_get_clientsession(hass), "secret")

    favorites = await client.get_favorites()

    assert favorites.name == "Favorites"
    assert favorites.station_ids == ("station-1",)


async def test_client_sends_user_agent(hass, aioclient_mock) -> None:
    """Send the library version in the default User-Agent header."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    client = Client(async_get_clientsession(hass), "secret")

    await client.get_favorites()

    headers = aioclient_mock.mock_calls[-1][3]
    assert headers["User-Agent"] == "commonsradio-python/0.1.0"


def test_vendored_client_matches_package() -> None:
    """Keep the HACS copy equal to the future PyPI package."""
    root = Path(__file__).parents[1]
    package = root / "commonsradio" / "src" / "commonsradio"
    vendored = root / "custom_components" / "commons_radio" / "commonsradio"

    for filename in ("__init__.py", "client.py", "models.py"):
        assert (package / filename).read_bytes() == (vendored / filename).read_bytes()


async def test_client_sends_key_only_to_private_routes(hass, aioclient_mock) -> None:
    """Send no key to public station routes, so the CDN can cache them."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1/schedule", json=schedule("Show"))
    aioclient_mock.get(
        f"{BASE_URL}/stations",
        json={"stations": [], "hasMore": False, "limit": 20, "offset": 0},
    )
    client = Client(async_get_clientsession(hass), "secret")

    await client.get_favorites()
    await client.get_station("station-1")
    await client.get_schedule("station-1")
    await client.list_stations()

    headers = [call[3] for call in aioclient_mock.mock_calls]
    assert headers[0]["Authorization"] == "Bearer secret"
    assert all("Authorization" not in item for item in headers[1:])
    assert all(item["User-Agent"] for item in headers)
