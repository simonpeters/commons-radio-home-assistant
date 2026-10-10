"""Tests for the Commons Radio play action."""

from __future__ import annotations

import pytest
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_EXTRA,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.media_player.const import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.components.websocket_api.automation import (
    async_get_services_for_target,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.commons_radio import SERVICE_PLAY
from custom_components.commons_radio.const import CONF_API_KEY, DOMAIN

from .fixtures import BASE_URL, collection, station


async def _setup_entry(
    hass, aioclient_mock, *, enable_sensor: bool = False
) -> MockConfigEntry:
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
    if enable_sensor:
        er.async_get(hass).async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_station-1_on_air",
            suggested_object_id="commons_radio_station_1_on_air",
        )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


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
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await _call_play(hass, station=value)

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: ["media_player.kitchen"],
        ATTR_MEDIA_CONTENT_ID: "https://stream.example/station.mp3",
        ATTR_MEDIA_CONTENT_TYPE: "audio/mpeg",
        ATTR_MEDIA_EXTRA: {
            "title": station_response["name"],
            "thumb": station_response["logoUrl"],
        },
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
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

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
    aioclient_mock.get(f"{BASE_URL}/stations/station-2", json=station("station-2"))
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await _call_play(hass, collection="morning")

    assert calls[0].data == {
        ATTR_ENTITY_ID: ["media_player.kitchen"],
        ATTR_MEDIA_CONTENT_ID: "https://stream.example/station.mp3",
        ATTR_MEDIA_CONTENT_TYPE: "audio/mpeg",
        ATTR_MEDIA_EXTRA: {
            "title": "Station One",
            "thumb": "https://images.example/station-2.png",
        },
    }


async def test_play_favorites(hass, aioclient_mock) -> None:
    """Play a random favorite station."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await _call_play(hass, favorites=True)

    assert calls[0].data == {
        ATTR_ENTITY_ID: ["media_player.kitchen"],
        ATTR_MEDIA_CONTENT_ID: "https://stream.example/station.mp3",
        ATTR_MEDIA_CONTENT_TYPE: "audio/mpeg",
        ATTR_MEDIA_EXTRA: {
            "title": "Station One",
            "thumb": "https://images.example/station-1.png",
        },
    }


def _media(identifier: str) -> dict[str, str]:
    """Build a media selector value for one Commons Radio item."""
    return {
        ATTR_MEDIA_CONTENT_ID: f"media-source://{DOMAIN}/{identifier}",
        ATTR_MEDIA_CONTENT_TYPE: "music",
    }


async def test_play_picked_station(hass, aioclient_mock) -> None:
    """Play a station selected with the media picker."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-2",
        json=station("station-2", name="Station Two"),
    )
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await _call_play(hass, media=_media("station/station-2"))

    assert calls[0].data[ATTR_MEDIA_CONTENT_ID] == (
        "https://stream.example/station.mp3"
    )
    assert calls[0].data[ATTR_MEDIA_EXTRA]["title"] == "Station Two"


async def test_play_picked_collection(hass, aioclient_mock) -> None:
    """Play a collection selected with the media picker."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(
        f"{BASE_URL}/me/collections/morning-id",
        json=collection(
            "morning-id",
            name="Morning",
            favorite=False,
            station_ids=["station-2"],
        ),
    )
    aioclient_mock.get(f"{BASE_URL}/stations/station-2", json=station("station-2"))
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await _call_play(hass, media=_media("collection/morning-id"))

    assert calls[0].data[ATTR_MEDIA_CONTENT_ID] == (
        "https://stream.example/station.mp3"
    )


async def test_play_picked_favorites(hass, aioclient_mock) -> None:
    """Play Favorites selected with the media picker."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await _call_play(hass, media=_media("favorites"))

    assert calls[0].data[ATTR_MEDIA_CONTENT_ID] == (
        "https://stream.example/station.mp3"
    )


async def test_play_forwards_a_speaker_device_target(hass, aioclient_mock) -> None:
    """Play on the media player of a speaker device target."""
    await _setup_entry(hass, aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/stations/station-2", json=station("station-2"))
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)
    speaker_entry = MockConfigEntry(domain="test")
    speaker_entry.add_to_hass(hass)
    speaker = dr.async_get(hass).async_get_or_create(
        config_entry_id=speaker_entry.entry_id,
        identifiers={("test", "speaker")},
    )
    er.async_get(hass).async_get_or_create(
        MEDIA_PLAYER_DOMAIN,
        "test",
        "speaker",
        suggested_object_id="speaker",
        device_id=speaker.id,
        config_entry=speaker_entry,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY,
        {"station": "station-2"},
        target={ATTR_DEVICE_ID: [speaker.id]},
        blocking=True,
    )

    assert calls[0].data[ATTR_ENTITY_ID] == ["media_player.speaker"]


async def test_play_rejects_other_media_source(hass) -> None:
    """Explain that the picker value must come from Commons Radio."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as error:
        await _call_play(
            hass,
            media={
                ATTR_MEDIA_CONTENT_ID: "media-source://radio_browser/station/one",
                ATTR_MEDIA_CONTENT_TYPE: "music",
            },
        )

    assert error.value.translation_key == "invalid_media_source"


async def test_play_action_metadata(hass) -> None:
    """Put the media picker first and link the action to both target types."""
    assert await async_setup_component(hass, DOMAIN, {})

    descriptions = await async_get_all_descriptions(hass)
    play = descriptions[DOMAIN][SERVICE_PLAY]

    assert next(iter(play["fields"])) == "media"
    assert play["fields"]["media"]["selector"] == {
        "media": {"accept": ["*"], "multiple": False}
    }
    assert play["target"]["entity"] == [
        {"domain": ["media_player"]},
        {"domain": ["sensor"], "integration": "commons_radio"},
    ]


async def test_play_action_is_available_for_service_device(
    hass, aioclient_mock
) -> None:
    """Show the play action for the service device with an enabled sensor."""
    entry = await _setup_entry(hass, aioclient_mock, enable_sensor=True)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None

    services = await async_get_services_for_target(
        hass,
        {ATTR_DEVICE_ID: [device.id]},
        expand_group=True,
    )

    assert f"{DOMAIN}.{SERVICE_PLAY}" in services


async def test_play_needs_a_speaker_in_the_target(hass, aioclient_mock) -> None:
    """Refuse a target with only the Commons Radio device and no speaker."""
    entry = await _setup_entry(hass, aioclient_mock, enable_sensor=True)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    calls = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY,
            {ATTR_DEVICE_ID: [device.id], "favorites": True},
            blocking=True,
        )

    assert error.value.translation_key == "no_media_player"
    assert calls == []


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"station": "one", "collection": "Morning"},
        {"media": _media("station/one"), "station": "one"},
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
