from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Airport:
    """An airport served by Ryanair."""

    iata: str
    name: str
    country_code: str
    time_zone: str
    is_base: bool


@dataclass(frozen=True, slots=True)
class FareObservation:
    """The cheapest fare for one outbound date, as last observed by Hermes.

    This is a scraped observation taken at ``observed_at``, not a live offer.
    """

    origin: str
    destination: str
    outbound_date: date
    departure: datetime
    arrival: datetime
    price: Decimal
    currency: str
    observed_at: datetime


class RouteNotFoundError(Exception):
    """Raised when Ryanair does not fly between two airports."""

    def __init__(self, origin: str, destination: str) -> None:
        super().__init__(f"No Ryanair route {origin}-{destination}")


class NoFaresObservedError(Exception):
    """Raised when a route exists but Hermes has no fare observations for it."""

    def __init__(self, origin: str, destination: str) -> None:
        super().__init__(f"No fares observed yet for {origin}-{destination}")


class UpstreamError(Exception):
    """Raised when Hermes fails or returns something unusable."""

    def __init__(self, message: str = "Hermes request failed") -> None:
        super().__init__(message)


class UpstreamTimeoutError(UpstreamError):
    """Raised when Hermes does not answer within the configured timeout."""

    def __init__(self) -> None:
        super().__init__("Hermes did not respond in time")
