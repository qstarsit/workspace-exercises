import logging
from datetime import date

import httpx
from pydantic import BaseModel, ValidationError

from fare_watch.domain import (
    Airport,
    FareObservation,
    NoFaresObservedError,
    RouteNotFoundError,
    UpstreamError,
    UpstreamTimeoutError,
)

logger = logging.getLogger(__name__)

AIRPORT_PAGE_SIZE = 1000


class _AirportList(BaseModel):
    items: list[Airport]


class _CheapestDay(BaseModel):
    fare: FareObservation


class _Cheapest(BaseModel):
    days: list[_CheapestDay]


class _CheapestNotFound(BaseModel):
    reason: str


def _parse[ModelT: BaseModel](model: type[ModelT], response: httpx.Response) -> ModelT:
    try:
        return model.model_validate_json(response.content)
    except ValidationError as exc:
        logger.error("Unexpected Hermes payload from %s: %s", response.url, exc)
        raise UpstreamError("Hermes returned an unexpected response") from exc


class HttpHermesClient:
    """``HermesClient`` implementation that talks to Hermes over HTTP.

    Args:
        http: Client configured with the Hermes base URL, timeout and headers.
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def list_airports(self, country: str | None = None) -> list[Airport]:
        """List airports, optionally limited to one country.

        Args:
            country: ISO 3166-1 alpha-2 country code, e.g. ``"nl"``.

        Returns:
            The matching airports.

        Raises:
            UpstreamError: If Hermes fails.
        """
        params = {"limit": str(AIRPORT_PAGE_SIZE)}
        if country is not None:
            params["country"] = country.lower()
        response = await self._get("airports/", params)
        return _parse(_AirportList, response).items

    async def cheapest_fares(
        self, origin: str, destination: str, on: date | None = None
    ) -> list[FareObservation]:
        """Get the latest observed cheapest fare per outbound date on a route.

        Args:
            origin: IATA code of the departure airport.
            destination: IATA code of the arrival airport.
            on: Only return the fare for this outbound date.

        Returns:
            One observation per outbound date that has data, ordered by date.

        Raises:
            RouteNotFoundError: If there is no such route.
            NoFaresObservedError: If the route has no observations yet.
            UpstreamError: If Hermes fails.
        """
        params = {} if on is None else {"on": on.isoformat()}
        response = await self._get(
            f"routes/{origin}/{destination}/cheapest", params, allow_not_found=True
        )
        if response.status_code == httpx.codes.NOT_FOUND:
            if _parse(_CheapestNotFound, response).reason == "route_unknown":
                raise RouteNotFoundError(origin, destination)
            raise NoFaresObservedError(origin, destination)
        return [day.fare for day in _parse(_Cheapest, response).days]

    async def _get(
        self, path: str, params: dict[str, str], *, allow_not_found: bool = False
    ) -> httpx.Response:
        try:
            response = await self._http.get(path, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Hermes timed out on %s", path)
            raise UpstreamTimeoutError from exc
        except httpx.HTTPError as exc:
            logger.error("Hermes request to %s failed: %s", path, exc)
            raise UpstreamError from exc
        if response.is_success or (
            allow_not_found and response.status_code == httpx.codes.NOT_FOUND
        ):
            return response
        logger.error("Hermes returned HTTP %s for %s", response.status_code, path)
        raise UpstreamError(f"Hermes returned HTTP {response.status_code}")
