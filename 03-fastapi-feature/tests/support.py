from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from fare_watch.domain import Airport, FareObservation, RouteNotFoundError

HERMES_URL = "https://hermes.test"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "hermes"

type HistoryFactory = Callable[[Sequence[tuple[str, str]]], dict[str, object]]


class FakeHermesClient:
    """In-memory stand-in for the Hermes client, injected via dependency_overrides."""

    def __init__(
        self,
        airports: Sequence[Airport] = (),
        fares: Sequence[FareObservation] = (),
    ) -> None:
        self.airports = list(airports)
        self.fares = list(fares)

    async def list_airports(self, country: str | None = None) -> list[Airport]:
        return [
            airport
            for airport in self.airports
            if country is None or airport.country_code == country
        ]

    async def cheapest_fares(
        self, origin: str, destination: str, on: date | None = None
    ) -> list[FareObservation]:
        route = [
            fare
            for fare in self.fares
            if (fare.origin, fare.destination) == (origin, destination)
        ]
        if not route:
            raise RouteNotFoundError(origin, destination)
        return [fare for fare in route if on is None or fare.outbound_date == on]
