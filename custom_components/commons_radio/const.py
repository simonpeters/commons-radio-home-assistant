"""Constants for the Commons Radio integration."""

from typing import Final

from .commonsradio import DEFAULT_USER_AGENT

DOMAIN: Final = "commons_radio"
CONF_API_KEY: Final = "api_key"
TITLE: Final = "Commons Radio"
FAVORITES: Final = "favorites"
COLLECTION_PREFIX: Final = "collection/"
STATION_PREFIX: Final = "station/"
# Schedules change at the hour or the half hour, so five minutes is enough.
UPDATE_INTERVAL_SECONDS: Final = 5 * 60
SCHEDULE_PARALLEL_LIMIT: Final = 5
STATION_CACHE_SECONDS: Final = 60 * 60
USER_AGENT: Final = f"{DEFAULT_USER_AGENT} HomeAssistant"
