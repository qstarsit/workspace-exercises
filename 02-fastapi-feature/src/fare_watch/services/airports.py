from fare_watch.clients.base import HermesClient
from fare_watch.domain import Airport


class AirportService:
    """Use cases for airports.

    Args:
        client: Hermes API client.
    """

    def __init__(self, client: HermesClient) -> None:
        self._client = client

    async def list_airports(self, country: str | None = None) -> list[Airport]:
        """List Ryanair airports, optionally for one country.

        Args:
            country: ISO 3166-1 alpha-2 country code.

        Returns:
            The matching airports, ordered by IATA code.
        """
        airports = await self._client.list_airports(country)
        return sorted(airports, key=lambda airport: airport.iata)
