from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
import respx

from fare_watch.clients.hermes import HttpHermesClient
from fare_watch.domain import (
    Airport,
    FareObservation,
    NoFaresObservedError,
    RouteNotFoundError,
    UpstreamError,
    UpstreamTimeoutError,
)
from tests.support import HERMES_URL

pytestmark = pytest.mark.anyio

CHEAPEST_PATH = "/routes/EIN/AGP/cheapest"


@pytest.fixture
async def hermes_client(hermes: respx.MockRouter) -> AsyncIterator[HttpHermesClient]:
    async with httpx.AsyncClient(base_url=f"{HERMES_URL}/api/v1") as http:
        yield HttpHermesClient(http)


async def test_list_airports_parses_payload_and_sends_filters(
    hermes_client: HttpHermesClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
) -> None:
    route = hermes.get("/airports/").respond(
        200, content=hermes_payload("airports_nl.json")
    )

    airports = await hermes_client.list_airports("NL")

    assert airports[1] == Airport(
        iata="EIN",
        name="Eindhoven",
        country_code="nl",
        time_zone="Europe/Amsterdam",
        is_base=True,
    )
    assert dict(route.calls.last.request.url.params) == {
        "country": "nl",
        "limit": "1000",
    }


async def test_cheapest_fares_parses_observations(
    hermes_client: HttpHermesClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
) -> None:
    hermes.get(CHEAPEST_PATH).respond(
        200, content=hermes_payload("cheapest_ein_agp.json")
    )

    fares = await hermes_client.cheapest_fares("EIN", "AGP")

    assert len(fares) == 5
    assert fares[0] == FareObservation(
        origin="EIN",
        destination="AGP",
        outbound_date=date(2026, 11, 25),
        departure=datetime(2026, 11, 25, 12, 30, tzinfo=UTC),
        arrival=datetime(2026, 11, 25, 15, 25, tzinfo=UTC),
        price=Decimal("169.99"),
        currency="EUR",
        observed_at=datetime(2026, 11, 25, 6, 7, 16, 412319, tzinfo=UTC),
    )


async def test_cheapest_fares_sends_outbound_date(
    hermes_client: HttpHermesClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
) -> None:
    route = hermes.get(CHEAPEST_PATH).respond(
        200, content=hermes_payload("cheapest_ein_agp_2026-12-10.json")
    )

    await hermes_client.cheapest_fares("EIN", "AGP", date(2026, 12, 10))

    assert route.calls.last.request.url.params["on"] == "2026-12-10"


@pytest.mark.parametrize(
    ("fixture_name", "error_type"),
    [
        ("cheapest_route_unknown.json", RouteNotFoundError),
        ("cheapest_no_observations.json", NoFaresObservedError),
    ],
)
async def test_cheapest_fares_maps_not_found_reasons(
    hermes_client: HttpHermesClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
    fixture_name: str,
    error_type: type[Exception],
) -> None:
    hermes.get(CHEAPEST_PATH).respond(404, content=hermes_payload(fixture_name))

    with pytest.raises(error_type):
        await hermes_client.cheapest_fares("EIN", "AGP")


@pytest.mark.parametrize(
    ("mock_response", "error_type"),
    [
        (httpx.Response(503), UpstreamError),
        (httpx.Response(429), UpstreamError),
        (httpx.Response(200, content=b"not json"), UpstreamError),
        (httpx.Response(200, json={"unexpected": True}), UpstreamError),
        (httpx.ConnectError("refused"), UpstreamError),
        (httpx.ReadTimeout("slow"), UpstreamTimeoutError),
    ],
)
async def test_upstream_failures_raise_upstream_errors(
    hermes_client: HttpHermesClient,
    hermes: respx.MockRouter,
    mock_response: httpx.Response | Exception,
    error_type: type[Exception],
) -> None:
    hermes.get("/airports/").mock(side_effect=[mock_response])

    with pytest.raises(error_type):
        await hermes_client.list_airports()
