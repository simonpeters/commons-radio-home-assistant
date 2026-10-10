"""API response fixtures for Commons Radio tests."""

from __future__ import annotations

from typing import Any

BASE_URL = "https://www.commonsradio.eu/api/v1"


def station(
    station_id: str = "station-1",
    *,
    name: str = "Station One",
    country: str | None = "Belgium",
    stream_url: str = "https://stream.example/station.mp3",
) -> dict[str, Any]:
    """Return one station response."""
    return {
        "id": station_id,
        "slug": station_id,
        "name": name,
        "country": country,
        "city": "Brussels",
        "language": "en",
        "logoUrl": f"https://images.example/{station_id}.png",
        "streamUrl": stream_url,
        "homepage": f"https://{station_id}.example",
    }


def collection(
    collection_id: str = "favorites",
    *,
    name: str = "Favorites",
    favorite: bool = True,
    station_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return one collection response."""
    return {
        "id": collection_id,
        "slug": collection_id,
        "name": name,
        "description": None,
        "imageUrl": None,
        "isFavorite": favorite,
        "playInOrder": False,
        "stationIds": station_ids if station_ids is not None else ["station-1"],
    }


def schedule(current_title: str | None = "Morning Show") -> dict[str, Any]:
    """Return one schedule summary response."""
    current = None
    if current_title is not None:
        current = {
            "title": current_title,
            "host": "Alex",
            "start": "2026-10-10T08:00:00Z",
            "end": "2026-10-10T10:00:00Z",
        }
    return {
        "now": current,
        "next": {
            "title": "Next Show",
            "start": "2026-10-10T10:00:00Z",
            "end": "2026-10-10T12:00:00Z",
        },
        "upcoming": [],
        "fetchedAt": "2026-10-10T09:00:00Z",
        "timezone": "Europe/Brussels",
    }
