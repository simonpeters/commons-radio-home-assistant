"""Tests for Commons Radio on-air sensors."""

from __future__ import annotations

import pytest
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

    state = hass.states.get("sensor.station_one_on_air")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["next_show"] == "Next Show"
    assert state.attributes["next_show_start"] == "2026-10-10T10:00:00Z"
