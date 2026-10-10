"""Tests for the Commons Radio media source."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from homeassistant.components.media_source import MediaSourceItem
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commons_radio import CommonsRadioRuntimeData
from custom_components.commons_radio.commonsradio import Client
from custom_components.commons_radio.const import CONF_API_KEY, DOMAIN
from custom_components.commons_radio.media_source import async_get_media_source

from .fixtures import BASE_URL, collection, station


def _add_entry(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        title="Commons Radio",
        unique_id=DOMAIN,
    )
    entry.runtime_data = CommonsRadioRuntimeData(
        Client(async_get_clientsession(hass), "key"), Mock()
    )
    entry.add_to_hass(hass)


def _item(hass, identifier: str | None) -> MediaSourceItem:
    return MediaSourceItem(hass, DOMAIN, identifier, None)


async def test_media_source_tree_and_resolve(hass, aioclient_mock) -> None:
    """Browse root and Favorites, then resolve a playable stream."""
    _add_entry(hass)
    source = await async_get_media_source(hass)

    root = await source.async_browse_media(_item(hass, ""))
    assert [child.title for child in root.children] == [
        "Favorites",
        "My collections",
        "Popular stations",
    ]
    assert root.children[0].can_play is True
    assert root.children[0].can_expand is True

    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    favorites = await source.async_browse_media(_item(hass, "favorites"))
    assert favorites.can_play is True
    assert favorites.can_expand is True
    assert len(favorites.children) == 1
    assert favorites.children[0].title == "Station One"
    assert favorites.children[0].thumbnail.endswith("station-1.png")

    aioclient_mock.get(
        f"{BASE_URL}/me/collections",
        json=[
            collection(),
            collection(
                "collection-1",
                name="Late nights",
                favorite=False,
                station_ids=["station-1"],
            ),
        ],
    )
    collections = await source.async_browse_media(_item(hass, "collections"))
    assert [child.title for child in collections.children] == ["Late nights"]
    assert collections.children[0].can_play is True
    assert collections.children[0].can_expand is True

    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    media = await source.async_resolve_media(_item(hass, "station/station-1"))
    assert media.url == "https://stream.example/station.mp3"
    assert media.mime_type == "audio/mpeg"


async def test_browse_root_without_identifier(hass) -> None:
    """Browse the root when the media picker sends no identifier.

    The action's media picker opens media-source://commons_radio without a
    trailing slash, and Home Assistant then passes None as the identifier.
    """
    _add_entry(hass)
    source = await async_get_media_source(hass)

    root = await source.async_browse_media(_item(hass, None))

    assert [child.title for child in root.children] == [
        "Favorites",
        "My collections",
        "Popular stations",
    ]
    assert MediaSourceItem.from_uri(
        hass, f"media-source://{DOMAIN}", None
    ).identifier in (
        None,
        "",
    )


async def test_resolve_collection_picks_station_at_play_time(
    hass, aioclient_mock
) -> None:
    """Pick a random station when a collection starts."""
    _add_entry(hass)
    source = await async_get_media_source(hass)
    aioclient_mock.get(
        f"{BASE_URL}/me/collections/morning",
        json=collection(
            "morning",
            name="Morning",
            favorite=False,
            station_ids=["station-1", "station-2"],
        ),
    )
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-2",
        json=station("station-2", stream_url="https://stream.example/two.aac"),
    )

    with patch(
        "custom_components.commons_radio.media_source.random.choice",
        return_value="station-2",
    ):
        media = await source.async_resolve_media(_item(hass, "collection/morning"))

    assert media.url == "https://stream.example/two.aac"
    assert media.mime_type == "audio/aac"


async def test_resolve_collection_tries_another_station(hass, aioclient_mock) -> None:
    """Try another collection station when the first station fails."""
    _add_entry(hass)
    source = await async_get_media_source(hass)
    aioclient_mock.get(
        f"{BASE_URL}/me/collections/morning",
        json=collection(
            "morning",
            name="Morning",
            favorite=False,
            station_ids=["broken", "station-2"],
        ),
    )
    aioclient_mock.get(f"{BASE_URL}/stations/broken", status=500)
    aioclient_mock.get(f"{BASE_URL}/stations/station-2", json=station("station-2"))

    with patch(
        "custom_components.commons_radio.media_source.random.choice",
        side_effect=["broken", "station-2"],
    ):
        media = await source.async_resolve_media(_item(hass, "collection/morning"))

    assert media.url == "https://stream.example/station.mp3"


async def test_resolve_empty_collection(hass, aioclient_mock) -> None:
    """Explain that an empty collection cannot be played."""
    _add_entry(hass)
    source = await async_get_media_source(hass)
    aioclient_mock.get(
        f"{BASE_URL}/me/collections/empty",
        json=collection("empty", name="Empty", favorite=False, station_ids=[]),
    )

    with pytest.raises(Unresolvable, match="empty"):
        await source.async_resolve_media(_item(hass, "collection/empty"))
