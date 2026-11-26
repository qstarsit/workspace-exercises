from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fare_watch.domain import FareObservation
from tests.support import FakeHermesClient

CHEAPEST_PATH = "/routes/EIN/AGP/cheapest"


def test_fares_returns_observations(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
) -> None:
    hermes.get(CHEAPEST_PATH).respond(
        200, content=hermes_payload("cheapest_ein_agp.json")
    )

    response = client.get("/routes/EIN/AGP/fares")

    assert response.status_code == 200
    body = response.json()
    assert (body["origin"], body["destination"]) == ("EIN", "AGP")
    assert len(body["fares"]) == 5
    assert body["fares"][0] == {
        "outbound_date": "2026-11-25",
        "departure": "2026-11-25T12:30:00Z",
        "arrival": "2026-11-25T15:25:00Z",
        "price": "169.99",
        "currency": "EUR",
        "observed_at": "2026-11-25T06:07:16.412319Z",
    }


def test_fares_normalises_codes_and_forwards_date(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
) -> None:
    route = hermes.get(CHEAPEST_PATH).respond(
        200, content=hermes_payload("cheapest_ein_agp_2026-12-10.json")
    )

    response = client.get("/routes/ein/agp/fares", params={"on": "2026-12-10"})

    assert response.status_code == 200
    assert response.json()["origin"] == "EIN"
    assert [fare["price"] for fare in response.json()["fares"]] == ["106.99"]
    assert route.calls.last.request.url.params["on"] == "2026-12-10"


def test_fares_for_date_without_observations_is_empty(
    client: TestClient, hermes: respx.MockRouter
) -> None:
    hermes.get(CHEAPEST_PATH).respond(200, json={"days": []})

    response = client.get("/routes/EIN/AGP/fares", params={"on": "2026-01-01"})

    assert response.status_code == 200
    assert response.json()["fares"] == []


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/routes/EI/AGP/fares", {}),
        ("/routes/EIN/AG1/fares", {}),
        ("/routes/EIN/AGP/fares", {"on": "next-week"}),
    ],
)
def test_fares_rejects_invalid_input(
    client: TestClient, path: str, params: dict[str, str]
) -> None:
    response = client.get(path, params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("fixture_name", "detail"),
    [
        ("cheapest_route_unknown.json", "No Ryanair route EIN-AGP"),
        ("cheapest_no_observations.json", "No fares observed yet for EIN-AGP"),
    ],
)
def test_fares_unknown_route_or_no_data_returns_404(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
    fixture_name: str,
    detail: str,
) -> None:
    hermes.get(CHEAPEST_PATH).respond(404, content=hermes_payload(fixture_name))

    response = client.get("/routes/EIN/AGP/fares")

    assert response.status_code == 404
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("mock_response", "status_code", "detail"),
    [
        (httpx.Response(503), 502, "Hermes returned HTTP 503"),
        (httpx.ConnectTimeout("slow"), 504, "Hermes did not respond in time"),
    ],
)
def test_fares_upstream_failures_map_to_gateway_errors(
    client: TestClient,
    hermes: respx.MockRouter,
    mock_response: httpx.Response | Exception,
    status_code: int,
    detail: str,
) -> None:
    hermes.get(CHEAPEST_PATH).mock(side_effect=[mock_response])

    response = client.get("/routes/EIN/AGP/fares")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_fares_via_injected_fake_client(
    fake_client: TestClient, fake_hermes: FakeHermesClient
) -> None:
    fake_hermes.fares = [
        FareObservation(
            origin="EIN",
            destination="AGP",
            outbound_date=date(2026, 12, day),
            departure=datetime(2026, 12, day, 12, 45, tzinfo=UTC),
            arrival=datetime(2026, 12, day, 15, 40, tzinfo=UTC),
            price=Decimal("49.99"),
            currency="EUR",
            observed_at=datetime(2026, 11, 25, 6, tzinfo=UTC),
        )
        for day in (10, 11)
    ]

    response = fake_client.get("/routes/ein/agp/fares", params={"on": "2026-12-11"})

    assert [fare["outbound_date"] for fare in response.json()["fares"]] == [
        "2026-12-11"
    ]
