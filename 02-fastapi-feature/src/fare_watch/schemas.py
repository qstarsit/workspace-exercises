from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

IataCode = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", to_upper=True)]
CountryCode = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$", to_lower=True)]


class AirportRead(BaseModel):
    """Response body representing an airport."""

    model_config = ConfigDict(from_attributes=True)

    iata: str
    name: str
    country_code: str
    time_zone: str
    is_base: bool


class FareObservationRead(BaseModel):
    """Cheapest fare for one outbound date, as observed at ``observed_at``."""

    model_config = ConfigDict(from_attributes=True)

    outbound_date: date
    departure: datetime
    arrival: datetime
    price: Decimal
    currency: str
    observed_at: datetime


class RouteFaresRead(BaseModel):
    """Response body listing observed cheapest fares on a route."""

    origin: str
    destination: str
    fares: list[FareObservationRead]


class HealthRead(BaseModel):
    """Response body of the health check."""

    status: str
