from fastapi import APIRouter

from fare_watch.dependencies import AirportServiceDep
from fare_watch.schemas import AirportRead, CountryCode

router = APIRouter(prefix="/airports", tags=["airports"])


@router.get("")
async def list_airports(
    service: AirportServiceDep, country: CountryCode | None = None
) -> list[AirportRead]:
    """List Ryanair airports, optionally for one country.

    Args:
        service: Airport service.
        country: ISO 3166-1 alpha-2 country code, case-insensitive.

    Returns:
        The matching airports, ordered by IATA code.
    """
    airports = await service.list_airports(country)
    return [AirportRead.model_validate(airport) for airport in airports]
