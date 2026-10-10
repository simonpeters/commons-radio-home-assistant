"""Fetch favorite stations and their schedules."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .commonsradio import (
    Client,
    Collection,
    CommonsRadioError,
    ForbiddenError,
    RateLimitError,
    Schedule,
    Station,
    UnauthorizedError,
)
from .const import (
    SCHEDULE_PARALLEL_LIMIT,
    STATION_CACHE_SECONDS,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FavoriteStationData:
    """A favorite station and its schedule."""

    station: Station
    schedule: Schedule | None


@dataclass(frozen=True, slots=True)
class _CachedStation:
    """A station detail response and its fetch time."""

    station: Station
    fetched_at: float


class CommonsRadioCoordinator(DataUpdateCoordinator[dict[str, FavoriteStationData]]):
    """Coordinate favorites and schedules for enabled sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Client,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Commons Radio favorites",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.favorite_station_ids: tuple[str, ...] = ()
        self.listening_station_ids: set[str] = set()
        self.data = {}
        self._station_cache: dict[str, _CachedStation] = {}
        self._favorite_listeners: set[Callable[[tuple[str, ...]], None]] = set()

    @callback
    def async_add_favorites_listener(
        self, listener: Callable[[tuple[str, ...]], None]
    ) -> Callable[[], None]:
        """Listen for newly added favorite stations."""
        self._favorite_listeners.add(listener)
        return lambda: self._favorite_listeners.discard(listener)

    @callback
    def async_add_station_listener(self, station_id: str) -> None:
        """Include one station in schedule updates."""
        self.listening_station_ids.add(station_id)

    @callback
    def async_remove_station_listener(self, station_id: str) -> None:
        """Remove one station from schedule updates."""
        self.listening_station_ids.discard(station_id)

    def station_name(self, station_id: str) -> str:
        """Return a cached station name or its ID."""
        cached = self._station_cache.get(station_id)
        return cached.station.name if cached else station_id

    async def async_update_favorites(self, favorites: Collection) -> None:
        """Store favorites, fetch new station details, and notify listeners."""
        old_station_ids = set(self.favorite_station_ids)
        self.favorite_station_ids = favorites.station_ids
        new_station_ids = tuple(
            station_id
            for station_id in favorites.station_ids
            if station_id not in old_station_ids
        )
        await self._async_fetch_station_details(new_station_ids)
        self._station_cache = {
            station_id: cached
            for station_id, cached in self._station_cache.items()
            if station_id in favorites.station_ids
        }
        if new_station_ids:
            for listener in self._favorite_listeners:
                listener(new_station_ids)

    async def async_refresh_favorites(self) -> None:
        """Refresh favorites without fetching schedules."""
        try:
            favorites = await self.client.get_favorites()
        except CommonsRadioError:
            _LOGGER.warning("The hourly Favorites refresh failed", exc_info=True)
            return
        await self.async_update_favorites(favorites)

    async def _async_fetch_station_details(self, station_ids: tuple[str, ...]) -> None:
        """Fetch station details and let one failed station use its ID."""
        semaphore = asyncio.Semaphore(SCHEDULE_PARALLEL_LIMIT)
        refresh_time = monotonic()

        async def fetch(station_id: str) -> None:
            async with semaphore:
                try:
                    await self._async_get_station(station_id, refresh_time)
                except CommonsRadioError:
                    _LOGGER.warning(
                        "Could not load station %s during the Favorites refresh",
                        station_id,
                    )

        await asyncio.gather(*(fetch(station_id) for station_id in station_ids))

    async def _async_get_station(self, station_id: str, refresh_time: float) -> Station:
        """Return station details from the one-hour cache."""
        cached = self._station_cache.get(station_id)
        if (
            cached is not None
            and refresh_time - cached.fetched_at < STATION_CACHE_SECONDS
        ):
            return cached.station
        station = await self.client.get_station(station_id)
        self._station_cache[station_id] = _CachedStation(station, refresh_time)
        return station

    async def _async_update_data(self) -> dict[str, FavoriteStationData]:
        """Fetch favorites and schedules for enabled sensors."""
        try:
            favorites = await self.client.get_favorites()
            await self.async_update_favorites(favorites)
            semaphore = asyncio.Semaphore(SCHEDULE_PARALLEL_LIMIT)
            refresh_time = monotonic()
            station_ids = tuple(
                station_id
                for station_id in favorites.station_ids
                if station_id in self.listening_station_ids
            )

            async def fetch(station_id: str) -> FavoriteStationData:
                async with semaphore:
                    station, schedule = await asyncio.gather(
                        self._async_get_station(station_id, refresh_time),
                        self.client.get_schedule(station_id),
                    )
                return FavoriteStationData(station, schedule)

            results = await asyncio.gather(*(fetch(item) for item in station_ids))
        except (UnauthorizedError, ForbiddenError) as error:
            raise ConfigEntryAuthFailed from error
        except RateLimitError as error:
            raise UpdateFailed(str(error)) from error
        except CommonsRadioError as error:
            raise UpdateFailed(str(error)) from error

        return dict(zip(station_ids, results, strict=True))
