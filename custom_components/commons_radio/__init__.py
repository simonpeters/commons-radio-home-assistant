"""Set up the Commons Radio integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .commonsradio import Client
from .const import CONF_API_KEY, DOMAIN, USER_AGENT
from .coordinator import CommonsRadioCoordinator

PLATFORMS = [Platform.SENSOR]


@dataclass(slots=True)
class CommonsRadioRuntimeData:
    """Runtime objects for one config entry."""

    client: Client
    coordinator: CommonsRadioCoordinator


type CommonsRadioConfigEntry = ConfigEntry[CommonsRadioRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: CommonsRadioConfigEntry
) -> bool:
    """Set up Commons Radio from a config entry."""
    client = Client(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        user_agent=USER_AGENT,
    )
    coordinator = CommonsRadioCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = CommonsRadioRuntimeData(client, coordinator)
    _async_remove_station_devices(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _async_remove_station_devices(
    hass: HomeAssistant, entry: CommonsRadioConfigEntry
) -> None:
    """Remove the station devices that version 0.1.0 made before release."""
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if (DOMAIN, entry.entry_id) not in device.identifiers:
            registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )


async def async_unload_entry(
    hass: HomeAssistant, entry: CommonsRadioConfigEntry
) -> bool:
    """Unload a Commons Radio config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
