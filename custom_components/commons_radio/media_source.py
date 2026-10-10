"""Browse and resolve Commons Radio stations."""

from __future__ import annotations

import asyncio
import mimetypes
import random
from urllib.parse import quote, unquote, urlsplit

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from . import CommonsRadioConfigEntry
from .commonsradio import Client, Collection, CommonsRadioError, Station
from .const import (
    COLLECTION_PREFIX,
    DOMAIN,
    FAVORITES,
    SCHEDULE_PARALLEL_LIMIT,
    STATION_PREFIX,
    TITLE,
)

COLLECTIONS = "collections"
POPULAR = "popular"


async def async_get_media_source(hass: HomeAssistant) -> CommonsRadioMediaSource:
    """Create the Commons Radio media source."""
    return CommonsRadioMediaSource(hass)


class CommonsRadioMediaSource(MediaSource):
    """Browse Commons Radio from the Home Assistant media browser."""

    name = TITLE

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    @property
    def client(self) -> Client:
        """Return the client from the single supported config entry."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise BrowseError("Commons Radio is not configured.")
        entry: CommonsRadioConfigEntry = entries[0]
        return entry.runtime_data.client

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a station or collection item to a stream URL."""
        identifier = item.identifier.strip("/")
        try:
            if identifier == FAVORITES:
                collection = await self.client.get_favorites()
                return await self._resolve_collection(collection)
            if identifier.startswith(COLLECTION_PREFIX):
                collection_id = unquote(identifier.removeprefix(COLLECTION_PREFIX))
                collection = await self.client.get_collection(collection_id)
                return await self._resolve_collection(collection)
            if identifier.startswith(STATION_PREFIX):
                station_id = unquote(identifier.removeprefix(STATION_PREFIX))
                station = await self.client.get_station(station_id)
                return _play_media(station)
        except CommonsRadioError as error:
            raise Unresolvable("The Commons Radio item could not be loaded.") from error
        raise Unresolvable("This Commons Radio item cannot be played.")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return one level of the Commons Radio media tree."""
        identifier = item.identifier.strip("/")
        try:
            if not identifier:
                return self._root()
            if identifier == FAVORITES:
                favorites = await self.client.get_favorites()
                return await self._collection_folder(FAVORITES, "Favorites", favorites)
            if identifier == COLLECTIONS:
                return await self._collections()
            if identifier.startswith(COLLECTION_PREFIX):
                collection_id = unquote(identifier.removeprefix(COLLECTION_PREFIX))
                collection = await self.client.get_collection(collection_id)
                return await self._collection_folder(
                    identifier, collection.name, collection
                )
            if identifier == POPULAR:
                page = await self.client.list_stations(
                    sort_by="popular", limit=100, offset=0
                )
                return self._station_folder(POPULAR, "Popular stations", page.stations)
        except CommonsRadioError as error:
            raise BrowseError("Commons Radio could not load this folder.") from error
        raise BrowseError("Commons Radio folder not found.")

    def _root(self) -> BrowseMediaSource:
        """Build the fixed root folders."""
        root = _directory("", TITLE)
        root.children = [
            _directory(FAVORITES, "Favorites", can_play=True),
            _directory(COLLECTIONS, "My collections"),
            _directory(POPULAR, "Popular stations"),
        ]
        return root

    async def _collections(self) -> BrowseMediaSource:
        """Build the user's collection folders."""
        collections = await self.client.get_collections()
        folder = _directory(COLLECTIONS, "My collections")
        folder.children = [
            _directory(
                f"{COLLECTION_PREFIX}{quote(collection.id, safe='')}",
                collection.name,
                thumbnail=collection.image_url,
                can_play=True,
            )
            for collection in collections
            if not collection.is_favorite
        ]
        return folder

    async def _collection_folder(
        self, identifier: str, title: str, collection: Collection
    ) -> BrowseMediaSource:
        """Build a folder from a collection's station IDs."""
        stations = await self._fetch_stations(collection.station_ids)
        folder = self._station_folder(identifier, title, stations)
        folder.can_play = True
        return folder

    async def _resolve_collection(self, collection: Collection) -> PlayMedia:
        """Pick a working station from a collection."""
        remaining = list(collection.station_ids)
        if not remaining:
            message = f'The collection "{collection.name}" is empty.'
            raise Unresolvable(message)

        last_error: CommonsRadioError | None = None
        while remaining:
            station_id = random.choice(remaining)  # noqa: S311
            remaining.remove(station_id)
            try:
                return _play_media(await self.client.get_station(station_id))
            except CommonsRadioError as error:
                last_error = error

        message = f'No station in the collection "{collection.name}" could be loaded.'
        raise Unresolvable(message) from last_error

    async def _fetch_stations(
        self, station_ids: tuple[str, ...]
    ) -> tuple[Station, ...]:
        """Fetch station details with a small parallel limit."""
        semaphore = asyncio.Semaphore(SCHEDULE_PARALLEL_LIMIT)

        async def fetch(station_id: str) -> Station:
            async with semaphore:
                return await self.client.get_station(station_id)

        return tuple(await asyncio.gather(*(fetch(item) for item in station_ids)))

    def _station_folder(
        self, identifier: str, title: str, stations: tuple[Station, ...]
    ) -> BrowseMediaSource:
        """Build a folder of playable station items."""
        folder = _directory(identifier, title)
        folder.children = [_station_item(station) for station in stations]
        return folder


def _directory(
    identifier: str,
    title: str,
    *,
    thumbnail: str | None = None,
    can_play: bool = False,
) -> BrowseMediaSource:
    """Create one expandable folder."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier,
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.MUSIC,
        title=title,
        can_play=can_play,
        can_expand=True,
        children_media_class=MediaClass.DIRECTORY,
        thumbnail=thumbnail,
    )


def _station_item(station: Station) -> BrowseMediaSource:
    """Create one playable station item."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{STATION_PREFIX}{quote(station.id, safe='')}",
        media_class=MediaClass.MUSIC,
        media_content_type=_mime_type(station.stream_url),
        title=station.name,
        can_play=True,
        can_expand=False,
        thumbnail=station.logo_url,
    )


def _mime_type(stream_url: str) -> str:
    """Guess the stream MIME type and use MP3 as the safe default."""
    mime_type, _ = mimetypes.guess_type(urlsplit(stream_url).path)
    return mime_type or "audio/mpeg"


def _play_media(station: Station) -> PlayMedia:
    """Build resolved media for one station."""
    return PlayMedia(station.stream_url, _mime_type(station.stream_url))
