from datetime import date
from typing import Protocol

from fare_watch.domain import Airport, FareObservation


class HermesClient(Protocol):
    """Port to the Hermes flight-price API. Services depend on this, not on HTTP."""

    async def list_airports(self, country: str | None = None) -> list[Airport]:
        """List airports, optionally limited to one country.

        Args:
            country: ISO 3166-1 alpha-2 country code, e.g. ``"nl"``.

        Returns:
            The matching airports.

        Raises:
            UpstreamError: If Hermes fails.
        """
        ...

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
        ...
