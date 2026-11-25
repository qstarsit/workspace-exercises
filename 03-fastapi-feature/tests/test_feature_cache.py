import time
from collections.abc import Callable

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fare_watch.config import Settings
from fare_watch.main import create_app
from tests.support import HERMES_URL

FARES_URL = "/routes/EIN/AGP/fares"
CHEAPEST_PATH = "/routes/EIN/AGP/cheapest"


@pytest.fixture
def cheapest(
    hermes: respx.MockRouter, hermes_payload: Callable[[str], bytes]
) -> respx.Route:
    return hermes.get(CHEAPEST_PATH).respond(
        200, content=hermes_payload("cheapest_ein_agp.json")
    )


def test_repeated_request_is_served_from_cache(
    client: TestClient, cheapest: respx.Route
) -> None:
    first = client.get(FARES_URL)
    second = client.get(FARES_URL)

    assert second.status_code == 200
    assert second.json() == first.json()
    assert cheapest.call_count == 1


def test_query_parameters_are_part_of_the_cache_key(
    client: TestClient, cheapest: respx.Route
) -> None:
    client.get(FARES_URL)
    client.get(FARES_URL, params={"on": "2026-11-26"})
    client.get(FARES_URL, params={"on": "2026-11-26"})

    assert cheapest.call_count == 2


def test_airport_lists_are_cached_per_country(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
) -> None:
    airports = hermes.get("/airports/").respond(
        200, content=hermes_payload("airports_nl.json")
    )

    for _ in range(3):
        client.get("/airports", params={"country": "nl"})
    client.get("/airports")

    assert airports.call_count == 2


def test_failed_requests_are_not_cached(
    client: TestClient,
    hermes: respx.MockRouter,
    hermes_payload: Callable[[str], bytes],
) -> None:
    route = hermes.get(CHEAPEST_PATH).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, content=hermes_payload("cheapest_ein_agp.json")),
        ]
    )

    statuses = [client.get(FARES_URL).status_code for _ in range(3)]

    assert statuses == [502, 200, 200]
    assert route.call_count == 2


def test_entries_expire_after_configured_ttl(
    monkeypatch: pytest.MonkeyPatch, cheapest: respx.Route
) -> None:
    monkeypatch.setenv("HERMES_CACHE_TTL_SECONDS", "0.2")
    app = create_app(Settings(base_url=HERMES_URL, api_key=None, _env_file=None))

    with TestClient(app) as client:
        client.get(FARES_URL)
        client.get(FARES_URL)
        time.sleep(0.3)
        client.get(FARES_URL)

    assert cheapest.call_count == 2


def test_zero_ttl_disables_the_cache(
    monkeypatch: pytest.MonkeyPatch, cheapest: respx.Route
) -> None:
    def request_twice(ttl_seconds: str) -> None:
        monkeypatch.setenv("HERMES_CACHE_TTL_SECONDS", ttl_seconds)
        app = create_app(Settings(base_url=HERMES_URL, api_key=None, _env_file=None))
        with TestClient(app) as client:
            client.get(FARES_URL)
            client.get(FARES_URL)

    request_twice("300")
    assert cheapest.call_count == 1

    request_twice("0")
    assert cheapest.call_count == 3
