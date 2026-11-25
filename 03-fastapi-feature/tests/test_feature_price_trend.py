from collections.abc import Callable

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from tests.support import HistoryFactory

TREND_URL = "/routes/EIN/AGP/trend"
HISTORY_PATH = "/routes/EIN/AGP/history"


@pytest.mark.parametrize(
    ("params", "direction", "change_percent", "sample_size"),
    [
        ({}, "rising", 11.5, 56),
        ({"days": "14"}, "rising", 11.5, 56),
        ({"days": "1"}, "flat", 2.9, 4),
        ({"days": "90"}, "rising", 40.3, 302),
    ],
)
def test_trend_on_recorded_history(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
    params: dict[str, str],
    direction: str,
    change_percent: float,
    sample_size: int,
) -> None:
    history = hermes.get(HISTORY_PATH).respond(
        200, content=hermes_payload("history_ein_agp_2026-12-10.json")
    )

    response = client.get(TREND_URL, params={"outbound_date": "2026-12-10", **params})

    assert response.status_code == 200
    assert response.json() == {
        "origin": "EIN",
        "destination": "AGP",
        "outbound_date": "2026-12-10",
        "days": int(params.get("days", "14")),
        "direction": direction,
        "change_percent": change_percent,
        "sample_size": sample_size,
    }
    assert history.calls.last.request.url.params["outbound_date"] == "2026-12-10"


@pytest.mark.parametrize(
    ("points", "days", "direction", "change_percent", "sample_size"),
    [
        (
            [("2026-11-01T00:00:00Z", "100.00"), ("2026-11-10T00:00:00Z", "105.00")],
            14,
            "rising",
            5.0,
            2,
        ),
        (
            [("2026-11-01T00:00:00Z", "100.00"), ("2026-11-10T00:00:00Z", "95.00")],
            14,
            "falling",
            -5.0,
            2,
        ),
        (
            [("2026-11-01T00:00:00Z", "100.00"), ("2026-11-10T00:00:00Z", "104.90")],
            14,
            "flat",
            4.9,
            2,
        ),
        (
            [
                ("2026-11-01T00:00:00Z", "50.00"),
                ("2026-11-10T00:00:00Z", "100.00"),
                ("2026-11-12T00:00:00Z", "80.00"),
                ("2026-11-15T00:00:00Z", "100.00"),
            ],
            7,
            "flat",
            0.0,
            3,
        ),
        (
            [
                ("2026-11-07T23:59:59Z", "50.00"),
                ("2026-11-08T00:00:00Z", "100.00"),
                ("2026-11-15T00:00:00Z", "110.00"),
            ],
            7,
            "rising",
            10.0,
            2,
        ),
    ],
)
def test_trend_compares_first_and_last_price_in_window(
    client: TestClient,
    hermes: respx.MockRouter,
    make_history: HistoryFactory,
    points: list[tuple[str, str]],
    days: int,
    direction: str,
    change_percent: float,
    sample_size: int,
) -> None:
    hermes.get(HISTORY_PATH).respond(200, json=make_history(points))

    body = client.get(
        TREND_URL, params={"outbound_date": "2026-12-10", "days": str(days)}
    ).json()

    assert (body["direction"], body["change_percent"], body["sample_size"]) == (
        direction,
        change_percent,
        sample_size,
    )


@pytest.mark.parametrize(
    "points",
    [
        [],
        [("2026-11-10T00:00:00Z", "100.00")],
        [("2026-11-01T00:00:00Z", "90.00"), ("2026-11-10T00:00:00Z", "100.00")],
    ],
)
def test_trend_with_fewer_than_two_points_in_window_is_inconclusive(
    client: TestClient,
    hermes: respx.MockRouter,
    make_history: HistoryFactory,
    points: list[tuple[str, str]],
) -> None:
    hermes.get(HISTORY_PATH).respond(200, json=make_history(points))

    response = client.get(
        TREND_URL, params={"outbound_date": "2026-12-10", "days": "3"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == "insufficient_data"
    assert body["change_percent"] is None
    assert body["sample_size"] == min(len(points), 1)


def test_trend_upstream_timeout_returns_504(
    client: TestClient, hermes: respx.MockRouter
) -> None:
    hermes.get(HISTORY_PATH).mock(side_effect=httpx.ReadTimeout("slow"))

    response = client.get(TREND_URL, params={"outbound_date": "2026-12-10"})

    assert response.status_code == 504
    assert response.json() == {"detail": "Hermes did not respond in time"}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"outbound_date": "2026-12-10", "days": "0"},
        {"outbound_date": "2026-12-10", "days": "91"},
    ],
)
def test_trend_rejects_invalid_input(
    client: TestClient, params: dict[str, str]
) -> None:
    response = client.get(TREND_URL, params=params)

    assert response.status_code == 422
