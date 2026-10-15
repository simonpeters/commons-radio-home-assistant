"""Tests for the Commons Radio update coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, call

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.commons_radio.commonsradio import (
    Client,
    Collection,
    RateLimitError,
    Station,
)
from custom_components.commons_radio.coordinator import CommonsRadioCoordinator

from .fixtures import collection, station


def _collection(*station_ids: str) -> Collection:
    return Collection.from_dict(collection(station_ids=list(station_ids)))


def _station(station_id: str) -> Station:
    return Station.from_dict(station(station_id))


def _client() -> Mock:
    client = Mock(spec=Client)
    client.get_favorites = AsyncMock()
    client.get_station = AsyncMock()
    client.get_schedule = AsyncMock(return_value=None)
    return client


async def test_second_refresh_uses_cached_station_detail(hass) -> None:
    """Fetch schedules again but keep station details for one hour."""
    client = _client()
    client.get_station.return_value = _station("station-1")
    coordinator = CommonsRadioCoordinator(hass, client)
    coordinator.async_add_station_listener("station-1")
    await coordinator.async_update_favorites(_collection("station-1"))

    await coordinator._async_update_data()
    await coordinator._async_update_data()

    client.get_station.assert_awaited_once_with("station-1")
    assert client.get_schedule.await_count == 2


async def test_update_does_not_request_favorites(hass) -> None:
    """Fetch only schedules; the hourly refresh keeps the favorites current."""
    client = _client()
    client.get_station.return_value = _station("station-1")
    coordinator = CommonsRadioCoordinator(hass, client)
    coordinator.async_add_station_listener("station-1")
    await coordinator.async_update_favorites(_collection("station-1"))

    await coordinator._async_update_data()

    client.get_favorites.assert_not_awaited()
    client.get_schedule.assert_awaited_once_with("station-1")


async def test_new_favorite_fetches_one_station_detail(hass) -> None:
    """Fetch station details only for a favorite that was just added."""
    client = _client()
    client.get_favorites.side_effect = [
        _collection("station-1"),
        _collection("station-1", "station-2"),
    ]
    client.get_station.side_effect = [_station("station-1"), _station("station-2")]
    coordinator = CommonsRadioCoordinator(hass, client)
    coordinator.async_add_station_listener("station-1")
    coordinator.async_add_station_listener("station-2")

    await coordinator.async_refresh_favorites()
    await coordinator._async_update_data()
    await coordinator.async_refresh_favorites()
    await coordinator._async_update_data()

    assert client.get_station.await_args_list == [call("station-1"), call("station-2")]
    assert client.get_schedule.await_count == 3


async def test_rate_limit_is_update_failed(hass) -> None:
    """Treat a rate limit as an update failure, not an auth failure."""
    client = _client()
    client.get_station.return_value = _station("station-1")
    client.get_schedule.side_effect = RateLimitError("60")
    coordinator = CommonsRadioCoordinator(hass, client)
    coordinator.async_add_station_listener("station-1")
    await coordinator.async_update_favorites(_collection("station-1"))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
