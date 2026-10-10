"""Fetch favorite stations and their schedules."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .commonsradio import (
    Client,
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
    """Update favorite stations once per minute."""

    def __init__(self, hass: HomeAssistant, client: Client) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Commons Radio favorites",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self._station_cache: dict[str, _CachedStation] = {}

    async def _async_update_data(self) -> dict[str, FavoriteStationData]:
        """Fetch favorites and schedules with a small parallel limit."""
        try:
            favorites = await self.client.get_favorites()
            semaphore = asyncio.Semaphore(SCHEDULE_PARALLEL_LIMIT)
            refresh_time = monotonic()
            refreshed_cache = {
                station_id: cached
                for station_id, cached in self._station_cache.items()
                if station_id in favorites.station_ids
            }

            async def fetch(station_id: str) -> FavoriteStationData:
                async with semaphore:
                    cached = refreshed_cache.get(station_id)
                    if (
                        cached is None
                        or refresh_time - cached.fetched_at >= STATION_CACHE_SECONDS
                    ):
                        station, schedule = await asyncio.gather(
                            self.client.get_station(station_id),
                            self.client.get_schedule(station_id),
                        )
                        refreshed_cache[station_id] = _CachedStation(
                            station, refresh_time
                        )
                    else:
                        station = cached.station
                        schedule = await self.client.get_schedule(station_id)
                return FavoriteStationData(station, schedule)

            results = await asyncio.gather(
                *(fetch(station_id) for station_id in favorites.station_ids)
            )
        except (UnauthorizedError, ForbiddenError) as error:
            raise ConfigEntryAuthFailed from error
        except RateLimitError as error:
            raise UpdateFailed(str(error)) from error
        except CommonsRadioError as error:
            raise UpdateFailed(str(error)) from error

        self._station_cache = refreshed_cache
        return dict(zip(favorites.station_ids, results, strict=True))
