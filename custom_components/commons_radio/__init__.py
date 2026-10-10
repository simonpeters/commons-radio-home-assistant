"""Set up the Commons Radio integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .commonsradio import Client
from .const import CONF_API_KEY, USER_AGENT
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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CommonsRadioConfigEntry
) -> bool:
    """Unload a Commons Radio config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
