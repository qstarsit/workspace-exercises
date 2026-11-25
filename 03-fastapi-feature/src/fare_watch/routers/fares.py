from datetime import date

from fastapi import APIRouter

from fare_watch.dependencies import FareServiceDep
from fare_watch.schemas import FareObservationRead, IataCode, RouteFaresRead

router = APIRouter(prefix="/routes/{origin}/{destination}", tags=["fares"])


@router.get("/fares")
async def list_cheapest_fares(
    origin: IataCode,
    destination: IataCode,
    service: FareServiceDep,
    on: date | None = None,
) -> RouteFaresRead:
    """List the latest observed cheapest fare per outbound date on a route.

    Args:
        origin: IATA code of the departure airport, case-insensitive.
        destination: IATA code of the arrival airport, case-insensitive.
        service: Fare service.
        on: Only return the fare for this outbound date.

    Returns:
        The observed fares, ordered by outbound date.
    """
    fares = await service.cheapest_fares(origin, destination, on)
    return RouteFaresRead(
        origin=origin,
        destination=destination,
        fares=[FareObservationRead.model_validate(fare) for fare in fares],
    )
