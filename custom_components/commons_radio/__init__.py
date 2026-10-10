"""Set up the Commons Radio integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib.parse import quote

import voluptuous as vol
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.media_source import (
    async_resolve_media as async_resolve_media_source,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .commonsradio import (
    ApiError,
    Client,
    CommonsRadioError,
    ForbiddenError,
    Station,
    UnauthorizedError,
)
from .const import (
    COLLECTION_PREFIX,
    CONF_API_KEY,
    DOMAIN,
    FAVORITES,
    STATION_PREFIX,
    USER_AGENT,
)
from .coordinator import CommonsRadioCoordinator

PLATFORMS = [Platform.SENSOR]
SERVICE_PLAY = "play"
ATTR_STATION = "station"
ATTR_COLLECTION = "collection"
ATTR_FAVORITES = "favorites"


def _validate_play_data(data: dict) -> dict:
    """Require one valid media source field."""
    source_fields = {
        key for key in (ATTR_STATION, ATTR_COLLECTION, ATTR_FAVORITES) if key in data
    }
    valid = len(source_fields) == 1
    if ATTR_FAVORITES in source_fields:
        valid = valid and data[ATTR_FAVORITES] is True
    elif source_fields:
        valid = valid and bool(data[next(iter(source_fields))].strip())
    if not valid:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="select_one_source",
        )
    return data


PLAY_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(ATTR_STATION): cv.string,
            vol.Optional(ATTR_COLLECTION): cv.string,
            vol.Optional(ATTR_FAVORITES): cv.boolean,
        }
    ),
    _validate_play_data,
)


@dataclass(slots=True)
class CommonsRadioRuntimeData:
    """Runtime objects for one config entry."""

    client: Client
    coordinator: CommonsRadioCoordinator


type CommonsRadioConfigEntry = ConfigEntry[CommonsRadioRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Commons Radio action."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY,
        _async_play,
        schema=PLAY_SCHEMA,
    )
    return True


async def _async_play(call: ServiceCall) -> None:
    """Resolve Commons Radio media and play it on the target players."""
    hass = call.hass
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_configured",
        )
    client = entries[0].runtime_data.client

    if station_value := call.data.get(ATTR_STATION):
        station = await _async_find_station(client, station_value)
        identifier = f"{STATION_PREFIX}{quote(station.id, safe='')}"
    elif collection_value := call.data.get(ATTR_COLLECTION):
        collections = await client.get_collections()
        collection = next(
            (
                item
                for item in collections
                if item.id == collection_value
                or item.name.casefold() == collection_value.casefold()
            ),
            None,
        )
        if collection is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="collection_not_found",
            )
        identifier = f"{COLLECTION_PREFIX}{quote(collection.id, safe='')}"
    else:
        identifier = FAVORITES

    resolved = await async_resolve_media_source(
        hass, f"media-source://{DOMAIN}/{identifier}", None
    )
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: call.data[ATTR_ENTITY_ID],
            ATTR_MEDIA_CONTENT_ID: resolved.url,
            ATTR_MEDIA_CONTENT_TYPE: resolved.mime_type,
        },
        blocking=True,
        context=call.context,
    )


async def _async_find_station(client: Client, value: str) -> Station:
    """Find one station by ID, slug, or name."""
    try:
        return await client.get_station(value)
    except ApiError as error:
        if error.status != HTTPStatus.NOT_FOUND:
            raise

    page = await client.list_stations(query=value, limit=10)
    if not page.stations:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="station_not_found",
        )
    return next(
        (
            station
            for station in page.stations
            if station.name.casefold() == value.casefold()
        ),
        page.stations[0],
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: CommonsRadioConfigEntry
) -> bool:
    """Set up Commons Radio from a config entry."""
    client = Client(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        user_agent=USER_AGENT,
    )
    try:
        favorites = await client.get_favorites()
    except (UnauthorizedError, ForbiddenError) as error:
        raise ConfigEntryAuthFailed from error
    except CommonsRadioError as error:
        raise ConfigEntryNotReady(str(error)) from error
    coordinator = CommonsRadioCoordinator(hass, client)
    await coordinator.async_update_favorites(favorites)
    entry.runtime_data = CommonsRadioRuntimeData(client, coordinator)
    _async_remove_station_devices(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_refresh_favorites(_now: datetime) -> None:
        """Refresh the favorite station list once per hour."""
        await coordinator.async_refresh_favorites()

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            async_refresh_favorites,
            timedelta(hours=1),
        )
    )
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
