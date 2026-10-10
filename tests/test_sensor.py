"""Tests for Commons Radio on-air sensors."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.commons_radio.const import CONF_API_KEY, DOMAIN

from .fixtures import BASE_URL, collection, schedule, station


def _enable_on_air_sensor(
    hass, entry: MockConfigEntry, station_id: str = "station-1"
) -> None:
    """Create an enabled registry entry before platform setup."""
    er.async_get(hass).async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{entry.entry_id}_{station_id}_on_air",
        suggested_object_id=f"commons_radio_{station_id}_on_air",
    )


def _request_count(aioclient_mock, path: str) -> int:
    """Count mocked HTTP requests with one path suffix."""
    return sum(
        str(call[1]).split("?", maxsplit=1)[0].endswith(path)
        for call in aioclient_mock.mock_calls
    )


@pytest.mark.parametrize(
    ("current_title", "expected_state"),
    [("Morning Show", "Morning Show"), (None, "unknown")],
)
async def test_sensor_state_and_next_show(
    hass, aioclient_mock, current_title: str | None, expected_state: str
) -> None:
    """Expose current and next show data for a favorite station."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-1/schedule", json=schedule(current_title)
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        title="Commons Radio",
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    _enable_on_air_sensor(hass, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.commons_radio_station_1_on_air")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["friendly_name"] == "Commons Radio Station One"
    assert state.attributes["next_show"] == "Next Show"
    assert state.attributes["next_show_start"] == "2026-10-10T10:00:00Z"


async def test_sensor_entity_id_uses_station_name(hass, aioclient_mock) -> None:
    """Use only the station name for a new sensor."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    sensor = registry.async_get("sensor.commons_radio_station_one")
    assert sensor is not None
    assert sensor.original_name == "Station One"
    assert registry.async_get("sensor.commons_radio_station_1_on_air") is None


async def test_sensor_entity_id_falls_back_to_station_id(hass, aioclient_mock) -> None:
    """Use the station ID when its details fail to load during setup."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", status=500)
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get("sensor.commons_radio_station_1") is not None


def _entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        title="Commons Radio",
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    return entry


async def test_sensors_belong_to_one_service_device(hass, aioclient_mock) -> None:
    """Group all sensors under one service device, and drop old station devices."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-1/schedule", json=schedule("Morning Show")
    )
    entry = _entry(hass)
    registry = dr.async_get(hass)
    old_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "station-1")},
        name="Station One",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
    assert [device.identifiers for device in devices] == [{(DOMAIN, entry.entry_id)}]
    assert devices[0].entry_type is dr.DeviceEntryType.SERVICE
    assert devices[0].name == "Commons Radio"
    assert devices[0].model == "On-air service"
    assert registry.async_get(old_device.id) is None


async def test_sensor_is_unavailable_after_favorite_removal(
    hass, aioclient_mock
) -> None:
    """Show a removed favorite as unavailable instead of failing."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-1/schedule", json=schedule("Morning Show")
    )
    entry = _entry(hass)
    _enable_on_air_sensor(hass, entry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    empty = collection()
    empty["stationIds"] = []
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=empty)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.commons_radio_station_1_on_air")
    assert state is not None
    assert state.state == "unavailable"


async def test_disabled_sensors_do_not_poll(hass, aioclient_mock) -> None:
    """Do not request favorites or schedules while all sensors are disabled."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    entry = _entry(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    initial_calls = len(aioclient_mock.mock_calls)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == initial_calls
    assert hass.states.get("sensor.commons_radio_station_one") is None


async def test_enabled_sensors_debounce_first_refresh(hass, aioclient_mock) -> None:
    """Use one coordinator refresh when three enabled sensors start."""
    station_ids = ["station-1", "station-2", "station-3"]
    aioclient_mock.get(
        f"{BASE_URL}/me/favorites",
        json=collection(station_ids=station_ids),
    )
    entry = _entry(hass)
    for number, station_id in enumerate(station_ids, start=1):
        aioclient_mock.get(
            f"{BASE_URL}/stations/{station_id}",
            json=station(station_id, name=f"Station {number}"),
        )
        aioclient_mock.get(
            f"{BASE_URL}/stations/{station_id}/schedule",
            json=schedule(f"Show {number}"),
        )
        _enable_on_air_sensor(hass, entry, station_id)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # One request validates the entry. One debounced request updates all sensors.
    assert _request_count(aioclient_mock, "/me/favorites") == 2


async def test_hourly_refresh_adds_new_favorite_without_schedule(
    hass, aioclient_mock
) -> None:
    """Add a disabled sensor for a new favorite without loading a schedule."""
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=collection())
    aioclient_mock.get(f"{BASE_URL}/stations/station-1", json=station())
    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{BASE_URL}/me/favorites",
        json=collection(station_ids=["station-1", "station-2"]),
    )
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-2",
        json=station("station-2", name="Station Two"),
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1, seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)

    registry = er.async_get(hass)
    assert registry.async_get("sensor.commons_radio_station_two") is not None
    assert _request_count(aioclient_mock, "/schedule") == 0


async def test_update_fetches_schedule_for_enabled_sensor_only(
    hass, aioclient_mock
) -> None:
    """Fetch one schedule when one of three favorite sensors is enabled."""
    station_ids = ["station-1", "station-2", "station-3"]
    aioclient_mock.get(
        f"{BASE_URL}/me/favorites",
        json=collection(station_ids=station_ids),
    )
    entry = _entry(hass)
    for number, station_id in enumerate(station_ids, start=1):
        aioclient_mock.get(
            f"{BASE_URL}/stations/{station_id}",
            json=station(station_id, name=f"Station {number}"),
        )
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-1/schedule",
        json=schedule("Show 1"),
    )
    _enable_on_air_sensor(hass, entry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{BASE_URL}/me/favorites",
        json=collection(station_ids=station_ids),
    )
    aioclient_mock.get(
        f"{BASE_URL}/stations/station-1/schedule",
        json=schedule("Show 1"),
    )

    await entry.runtime_data.coordinator.async_refresh()

    assert _request_count(aioclient_mock, "/me/favorites") == 1
    assert _request_count(aioclient_mock, "/schedule") == 1
