"""Tests for Commons Radio on-air sensors."""

from __future__ import annotations

import pytest
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commons_radio.const import CONF_API_KEY, DOMAIN

from .fixtures import BASE_URL, collection, schedule, station


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

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.commons_radio_station_one_on_air")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["next_show"] == "Next Show"
    assert state.attributes["next_show_start"] == "2026-10-10T10:00:00Z"


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
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    empty = collection()
    empty["stationIds"] = []
    aioclient_mock.get(f"{BASE_URL}/me/favorites", json=empty)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.commons_radio_station_one_on_air")
    assert state is not None
    assert state.state == "unavailable"
