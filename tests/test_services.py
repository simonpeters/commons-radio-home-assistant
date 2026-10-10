"""Tests for the Commons Radio play action."""

from __future__ import annotations

import pytest
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.media_player.const import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commons_radio import SERVICE_PLAY
from custom_components.commons_radio.const import CONF_API_KEY, DOMAIN

from .fixtures import BASE_URL, collection, station


async def _setup_entry(hass, aioclient_mock) -> MockConfigEntry:
    """Set up one Commons Radio entry with mocked favorites."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        title="Commons Radio",
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _capture_play_media(hass) -> list[ServiceCall]:
    """Capture calls to the media player action."""
    calls: list[ServiceCall] = []

    async def capture(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        capture,
    )
    return calls


async def _call_play(hass, **data) -> None:
    """Call the Commons Radio action for one test player."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY,
        data,
        target={ATTR_ENTITY_ID: ["media_player.kitchen"]},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("value", "station_response"),
    [
        ("station-id", station("station-id")),
        ("station-slug", station("station-id", slug="station-slug")),
    ],
)
async def test_play_station_by_id_or_slug(
    hass, aioclient_mock, value: str, station_response: dict
) -> None:
    """Resolve a station ID or slug and play its stream URL."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/stations/{value}", json=station_response)
    aioclient_mock.get(
        f"{BASE_URL}/stations/{station_response['id']}", json=station_response
    )
    calls = _capture_play_media(hass)

    await _call_play(hass, station=value)

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: ["media_player.kitchen"],
        ATTR_MEDIA_CONTENT_ID: "https://stream.example/station.mp3",
        ATTR_MEDIA_CONTENT_TYPE: "audio/mpeg",
    }


async def test_play_station_by_name(hass, aioclient_mock) -> None:
    """Search after an ID lookup fails and prefer a matching station name."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/stations/My Station", status=404)
    aioclient_mock.get(
        f"{BASE_URL}/stations",
        json={
            "stations": [
                station("other", name="Other"),
                station("match", name="my station"),
            ],
            "hasMore": False,
            "limit": 10,
            "offset": 0,
        },
    )
    aioclient_mock.get(f"{BASE_URL}/stations/match", json=station("match"))
    calls = _capture_play_media(hass)

    await _call_play(hass, station="My Station")

    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].endswith("station.mp3")
    request_urls = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert any("q=My+Station" in url for url in request_urls)


async def test_play_collection_by_name(hass, aioclient_mock) -> None:
    """Resolve a collection name and play one station from it."""
    await _setup_entry(hass, aioclient_mock)
    morning = collection(
        "morning-id",
        name="Morning",
        favorite=False,
        station_ids=["station-2"],
    )
    aioclient_mock.get(f"{BASE_URL}/me/collections", json=[morning])
    aioclient_mock.get(f"{BASE_URL}/me/collections/morning-id", json=morning)
    aioclient_mock.get(f"{BASE_URL}/stations/station-2", json=station("station-2"))
    calls = _capture_play_media(hass)

    await _call_play(hass, collection="morning")

    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].endswith("station.mp3")


async def test_play_favorites(hass, aioclient_mock) -> None:
    """Play a random favorite station."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    calls = _capture_play_media(hass)

    await _call_play(hass, favorites=True)

    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].endswith("station.mp3")


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"station": "one", "collection": "Morning"},
        {"favorites": False},
        {"station": ""},
    ],
)
async def test_play_validates_one_source(hass, data: dict) -> None:
    """Reject missing, multiple, false, or empty source values."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as error:
        await _call_play(hass, **data)

    assert error.value.translation_key == "select_one_source"


async def test_play_requires_config_entry(hass) -> None:
    """Explain that the action needs a Commons Radio entry."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as error:
        await _call_play(hass, station="station-1")

    assert error.value.translation_key == "not_configured"


async def test_play_station_not_found(hass, aioclient_mock) -> None:
    """Report a station that does not match any search result."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/stations/missing", status=404)
    aioclient_mock.get(
        f"{BASE_URL}/stations",
        json={
            "stations": [],
            "hasMore": False,
            "limit": 10,
            "offset": 0,
        },
    )

    with pytest.raises(ServiceValidationError) as error:
        await _call_play(hass, station="missing")

    assert error.value.translation_key == "station_not_found"


async def test_play_collection_not_found(hass, aioclient_mock) -> None:
    """Report a collection that does not match an ID or name."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/me/collections", json=[])

    with pytest.raises(ServiceValidationError) as error:
        await _call_play(hass, collection="missing")

    assert error.value.translation_key == "collection_not_found"
