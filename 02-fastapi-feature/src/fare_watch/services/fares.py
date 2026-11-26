from datetime import date

from fare_watch.clients.base import HermesClient
from fare_watch.domain import FareObservation


class FareService:
    """Use cases for observed fares on a route.

    Args:
        client: Hermes API client.
    """

    def __init__(self, client: HermesClient) -> None:
        self._client = client

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
        return await self._client.cheapest_fares(origin, destination, on)
