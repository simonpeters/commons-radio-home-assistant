"""Async client for the Commons Radio public API."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import aiohttp

from .models import Collection, Schedule, Station, StationPage

DEFAULT_BASE_URL = "https://www.commonsradio.eu/api/v1"
__version__ = "0.1.0"
DEFAULT_USER_AGENT = f"commonsradio-python/{__version__}"


class CommonsRadioError(Exception):
    """Base class for Commons Radio client errors."""


class UnauthorizedError(CommonsRadioError):
    """The API key is missing or invalid."""


class ForbiddenError(CommonsRadioError):
    """The API key does not have the required scope."""


class RateLimitError(CommonsRadioError):
    """The API rate limit was reached."""

    def __init__(self, retry_after: str | None = None) -> None:
        """Store the optional Retry-After response value."""
        super().__init__("The Commons Radio API rate limit was reached")
        self.retry_after = retry_after


class ApiError(CommonsRadioError):
    """The API returned another unsuccessful response."""

    def __init__(self, status: int, message: str) -> None:
        """Store the response status and message."""
        super().__init__(f"Commons Radio API error {status}: {message}")
        self.status = status


class CommonsRadioConnectionError(CommonsRadioError):
    """The client could not reach or read the API."""


class Client:
    """Use the Commons Radio public API with a caller-owned session."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        """Initialize the client without taking ownership of the session."""
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent

    async def _get(
        self, path: str, *, authenticated: bool = True, **params: str | int
    ) -> Any:
        # Station routes are public. Without the Authorization header, the CDN
        # can serve them from its cache instead of running the API each time.
        headers = {"User-Agent": self._user_agent}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            async with self._session.get(
                f"{self._base_url}{path}", headers=headers, params=params or None
            ) as response:
                if response.status == HTTPStatus.UNAUTHORIZED:
                    raise UnauthorizedError
                if response.status == HTTPStatus.FORBIDDEN:
                    raise ForbiddenError
                if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                    raise RateLimitError(response.headers.get("Retry-After"))
                if response.status >= HTTPStatus.BAD_REQUEST:
                    raise ApiError(response.status, await response.text())
                try:
                    return await response.json()
                except (aiohttp.ContentTypeError, ValueError) as error:
                    raise ApiError(response.status, "Invalid JSON response") from error
        except CommonsRadioError:
            raise
        except (aiohttp.ClientError, TimeoutError) as error:
            raise CommonsRadioConnectionError from error

    async def get_favorites(self) -> Collection:
        """Return the authenticated user's Favorites collection."""
        return Collection.from_dict(await self._get("/me/favorites"))

    async def get_collections(self) -> tuple[Collection, ...]:
        """Return the authenticated user's collections."""
        data = await self._get("/me/collections")
        return tuple(Collection.from_dict(item) for item in data)

    async def get_collection(self, collection_id: str) -> Collection:
        """Return one authenticated user collection."""
        data = await self._get(f"/me/collections/{collection_id}")
        return Collection.from_dict(data)

    async def get_station(self, station_id_or_slug: str) -> Station:
        """Return one station by ID or slug."""
        data = await self._get(f"/stations/{station_id_or_slug}", authenticated=False)
        return Station.from_dict(data)

    async def list_stations(
        self,
        *,
        query: str | None = None,
        country: str | None = None,
        sort_by: str = "popular",
        limit: int = 20,
        offset: int = 0,
    ) -> StationPage:
        """Return one filtered page of stations."""
        params: dict[str, str | int] = {
            "sortBy": sort_by,
            "limit": limit,
            "offset": offset,
        }
        if query:
            params["q"] = query
        if country:
            params["country"] = country
        data = await self._get("/stations", authenticated=False, **params)
        return StationPage(
            stations=tuple(Station.from_dict(item) for item in data["stations"]),
            has_more=bool(data["hasMore"]),
            limit=int(data["limit"]),
            offset=int(data["offset"]),
        )

    async def get_schedule(self, station_id_or_slug: str) -> Schedule | None:
        """Return the station schedule summary, if the station has one."""
        data = await self._get(
            f"/stations/{station_id_or_slug}/schedule", authenticated=False
        )
        return Schedule.from_dict(data) if isinstance(data, dict) else None
