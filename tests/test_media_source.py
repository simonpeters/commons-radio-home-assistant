"""Tests for the Commons Radio media source."""

from __future__ import annotations

from unittest.mock import Mock

from homeassistant.components.media_source import MediaSourceItem
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


def _item(hass, identifier: str) -> MediaSourceItem:
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

    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    favorites = await source.async_browse_media(_item(hass, "favorites"))
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

    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    media = await source.async_resolve_media(_item(hass, "station/station-1"))
    assert media.url == "https://stream.example/station.mp3"
    assert media.mime_type == "audio/mpeg"
