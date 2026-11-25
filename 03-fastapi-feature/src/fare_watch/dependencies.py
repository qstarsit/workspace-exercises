from typing import Annotated

from fastapi import Depends, Request

from fare_watch.clients.base import HermesClient
from fare_watch.services.airports import AirportService
from fare_watch.services.fares import FareService


def get_hermes_client(request: Request) -> HermesClient:
    """Return the Hermes client created by the application lifespan.

    Args:
        request: The current request.

    Returns:
        The shared Hermes client.
    """
    client: HermesClient = request.app.state.hermes_client
    return client


HermesClientDep = Annotated[HermesClient, Depends(get_hermes_client)]


def get_airport_service(client: HermesClientDep) -> AirportService:
    """Build an airport service for the current request.

    Args:
        client: The Hermes client to use.

    Returns:
        An airport service bound to ``client``.
    """
    return AirportService(client)


def get_fare_service(client: HermesClientDep) -> FareService:
    """Build a fare service for the current request.

    Args:
        client: The Hermes client to use.

    Returns:
        A fare service bound to ``client``.
    """
    return FareService(client)


AirportServiceDep = Annotated[AirportService, Depends(get_airport_service)]
FareServiceDep = Annotated[FareService, Depends(get_fare_service)]
