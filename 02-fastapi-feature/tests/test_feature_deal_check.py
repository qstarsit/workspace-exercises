from collections.abc import Callable, Sequence

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from tests.support import HistoryFactory

DEAL_URL = "/routes/EIN/AGP/deal"
PARAMS = {"outbound_date": "2026-12-10"}
CHEAPEST_PATH = "/routes/EIN/AGP/cheapest"
HISTORY_PATH = "/routes/EIN/AGP/history"


@pytest.fixture
def current_fare(
    hermes: respx.MockRouter, hermes_payload: Callable[[str], bytes]
) -> respx.Route:
    """Hermes reports 106.99 EUR as the latest cheapest fare on 2026-12-10."""
    return hermes.get(CHEAPEST_PATH).respond(
        200, content=hermes_payload("cheapest_ein_agp_2026-12-10.json")
    )


def daily(prices: Sequence[str]) -> list[tuple[str, str]]:
    return [
        (f"2026-11-{day:02d}T06:00:00Z", price)
        for day, price in enumerate(prices, start=1)
    ]


def test_deal_check_on_recorded_history(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
    current_fare: respx.Route,
) -> None:
    history = hermes.get(HISTORY_PATH).respond(
        200, content=hermes_payload("history_ein_agp_2026-12-10.json")
    )

    response = client.get(DEAL_URL, params=PARAMS)

    assert response.status_code == 200
    assert response.json() == {
        "origin": "EIN",
        "destination": "AGP",
        "outbound_date": "2026-12-10",
        "price": "106.99",
        "currency": "EUR",
        "observed_at": "2026-11-25T06:07:16.412319Z",
        "verdict": "expensive",
        "percentile": 98.5,
        "sample_size": 302,
    }
    assert current_fare.calls.last.request.url.params["on"] == "2026-12-10"
    assert history.calls.last.request.url.params["outbound_date"] == "2026-12-10"


@pytest.mark.parametrize(
    ("history_prices", "verdict", "percentile"),
    [
        (["120.00", "130.00", "140.00", "150.00", "106.99"], "cheap", 10.0),
        (["100.00", "106.99", "110.00", "120.00", "90.00"], "normal", 50.0),
        (["50.00", "60.00", "70.00", "80.00", "106.99"], "expensive", 90.0),
        (["106.99"] * 5, "normal", 50.0),
        (["10.00", "20.00", "106.99", *["200.00"] * 7], "cheap", 25.0),
        ([*["10.00"] * 7, "106.99", "200.00", "300.00"], "expensive", 75.0),
    ],
)
def test_deal_verdict_follows_percentile_rank(
    client: TestClient,
    hermes: respx.MockRouter,
    make_history: HistoryFactory,
    current_fare: respx.Route,
    history_prices: list[str],
    verdict: str,
    percentile: float,
) -> None:
    hermes.get(HISTORY_PATH).respond(200, json=make_history(daily(history_prices)))

    body = client.get(DEAL_URL, params=PARAMS).json()

    assert (body["verdict"], body["percentile"]) == (verdict, percentile)
    assert body["sample_size"] == len(history_prices)


@pytest.mark.parametrize("sample_size", [0, 4])
def test_deal_with_too_little_history_is_inconclusive(
    client: TestClient,
    hermes: respx.MockRouter,
    make_history: HistoryFactory,
    current_fare: respx.Route,
    sample_size: int,
) -> None:
    hermes.get(HISTORY_PATH).respond(
        200, json=make_history(daily(["50.00"] * sample_size))
    )

    response = client.get(DEAL_URL, params=PARAMS)

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "insufficient_data"
    assert body["percentile"] is None
    assert body["sample_size"] == sample_size


def test_deal_without_current_fare_returns_404(
    client: TestClient, hermes: respx.MockRouter, make_history: HistoryFactory
) -> None:
    hermes.get(CHEAPEST_PATH).respond(200, json={"days": []})
    hermes.get(HISTORY_PATH).respond(200, json=make_history(daily(["50.00"] * 5)))

    response = client.get(DEAL_URL, params=PARAMS)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "No fares observed yet for EIN-AGP on 2026-12-10"
    }


def test_deal_for_unknown_route_returns_404(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
    make_history: HistoryFactory,
) -> None:
    hermes.get(CHEAPEST_PATH).respond(
        404, content=hermes_payload("cheapest_route_unknown.json")
    )
    hermes.get(HISTORY_PATH).respond(200, json=make_history([]))

    response = client.get(DEAL_URL, params=PARAMS)

    assert response.status_code == 404
    assert response.json() == {"detail": "No Ryanair route EIN-AGP"}


def test_deal_when_history_fails_returns_502(
    client: TestClient, hermes: respx.MockRouter, current_fare: respx.Route
) -> None:
    hermes.get(HISTORY_PATH).mock(return_value=httpx.Response(500))

    response = client.get(DEAL_URL, params=PARAMS)

    assert response.status_code == 502


@pytest.mark.parametrize(
    ("path", "params"),
    [
        (DEAL_URL, {}),
        (DEAL_URL, {"outbound_date": "soon"}),
        ("/routes/EINDHOVEN/AGP/deal", PARAMS),
    ],
)
def test_deal_rejects_invalid_input(
    client: TestClient, path: str, params: dict[str, str]
) -> None:
    response = client.get(path, params=params)

    assert response.status_code == 422
