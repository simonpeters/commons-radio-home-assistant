"""Typed models for the Commons Radio public API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    """Read an optional string field."""
    value = data.get(key)
    return value if isinstance(value, str) else None


@dataclass(frozen=True, slots=True)
class Station:
    """A public radio station."""

    id: str
    slug: str
    name: str
    country: str | None
    city: str | None
    language: str | None
    logo_url: str
    stream_url: str
    homepage: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Station:
        """Create a station from an API response."""
        return cls(
            id=str(data["id"]),
            slug=str(data["slug"]),
            name=str(data["name"]),
            country=_optional_string(data, "country"),
            city=_optional_string(data, "city"),
            language=_optional_string(data, "language"),
            logo_url=str(data["logoUrl"]),
            stream_url=str(data["streamUrl"]),
            homepage=_optional_string(data, "homepage"),
        )


@dataclass(frozen=True, slots=True)
class Collection:
    """A user collection of station IDs."""

    id: str
    slug: str | None
    name: str
    description: str | None
    image_url: str | None
    is_favorite: bool
    play_in_order: bool
    station_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Collection:
        """Create a collection from an API response."""
        station_ids = data.get("stationIds", [])
        return cls(
            id=str(data["id"]),
            slug=_optional_string(data, "slug"),
            name=str(data["name"]),
            description=_optional_string(data, "description"),
            image_url=_optional_string(data, "imageUrl"),
            is_favorite=bool(data["isFavorite"]),
            play_in_order=bool(data["playInOrder"]),
            station_ids=tuple(str(item) for item in station_ids),
        )


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    """One scheduled radio show."""

    title: str
    start: str
    end: str
    host: str | None = None
    description: str | None = None
    url: str | None = None
    image_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleSlot:
        """Create a schedule slot from an API response."""
        return cls(
            title=str(data["title"]),
            start=str(data["start"]),
            end=str(data["end"]),
            host=_optional_string(data, "host"),
            description=_optional_string(data, "description"),
            url=_optional_string(data, "url"),
            image_url=_optional_string(data, "imageUrl"),
        )


@dataclass(frozen=True, slots=True)
class Schedule:
    """The current and upcoming schedule for a station."""

    now: ScheduleSlot | None
    next: ScheduleSlot | None
    upcoming: tuple[ScheduleSlot, ...]
    fetched_at: str
    timezone: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Schedule:
        """Create a schedule from an API response."""
        now = data.get("now")
        next_slot = data.get("next")
        return cls(
            now=ScheduleSlot.from_dict(now) if isinstance(now, dict) else None,
            next=(
                ScheduleSlot.from_dict(next_slot)
                if isinstance(next_slot, dict)
                else None
            ),
            upcoming=tuple(
                ScheduleSlot.from_dict(item) for item in data.get("upcoming", [])
            ),
            fetched_at=str(data["fetchedAt"]),
            timezone=_optional_string(data, "timezone"),
        )


@dataclass(frozen=True, slots=True)
class StationPage:
    """One page of public stations."""

    stations: tuple[Station, ...]
    has_more: bool
    limit: int
    offset: int
