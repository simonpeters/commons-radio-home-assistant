"""On-air sensors for favorite Commons Radio stations."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CommonsRadioConfigEntry
from .const import DOMAIN
from .coordinator import CommonsRadioCoordinator, FavoriteStationData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CommonsRadioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one on-air sensor for each favorite station."""
    coordinator = entry.runtime_data.coordinator

    @callback
    def async_add_new_sensors(station_ids: tuple[str, ...]) -> None:
        """Add sensors after the Favorites refresh loads their names."""
        async_add_entities(
            CommonsRadioOnAirSensor(coordinator, entry.entry_id, station_id)
            for station_id in station_ids
        )

    async_add_new_sensors(coordinator.favorite_station_ids)
    entry.async_on_unload(
        coordinator.async_add_favorites_listener(async_add_new_sensors)
    )


class CommonsRadioOnAirSensor(CoordinatorEntity[CommonsRadioCoordinator], SensorEntity):
    """Show the current and next show for one favorite station."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:radio"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: CommonsRadioCoordinator,
        entry_id: str,
        station_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_unique_id = f"{entry_id}_{station_id}_on_air"
        self._attr_name = coordinator.station_name(station_id)
        # A station is not a device in the home. All sensors belong to one
        # service device, so Home Assistant does not ask for an area.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Commons Radio",
            manufacturer="Commons Radio",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.commonsradio.eu",
        )

    async def async_added_to_hass(self) -> None:
        """Start polling when this enabled sensor starts listening."""
        self.coordinator.async_add_station_listener(self._station_id)
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Stop schedule work when this sensor stops listening."""
        self.coordinator.async_remove_station_listener(self._station_id)
        await super().async_will_remove_from_hass()

    @property
    def available(self) -> bool:
        """Return False when the station is no longer a favorite."""
        return (
            super().available
            and self._station_id in self.coordinator.favorite_station_ids
        )

    @property
    def _station_data(self) -> FavoriteStationData | None:
        return self.coordinator.data.get(self._station_id)

    @property
    def native_value(self) -> str | None:
        """Return the current show title, or unknown when it is null."""
        data = self._station_data
        schedule = data.schedule if data else None
        return schedule.now.title if schedule and schedule.now else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details about the next show."""
        data = self._station_data
        schedule = data.schedule if data else None
        next_show = schedule.next if schedule else None
        if next_show is None:
            return {"next_show": None}
        return {
            "next_show": next_show.title,
            "next_show_start": next_show.start,
            "next_show_end": next_show.end,
        }
