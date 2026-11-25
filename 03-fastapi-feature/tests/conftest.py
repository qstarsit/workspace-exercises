from collections.abc import Callable, Iterator, Sequence

import pytest
import respx
from fastapi.testclient import TestClient

from fare_watch.config import Settings
from fare_watch.dependencies import get_hermes_client
from fare_watch.main import create_app
from tests.support import FIXTURES_DIR, HERMES_URL, FakeHermesClient, HistoryFactory


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def hermes_payload() -> Callable[[str], bytes]:
    """Load a recorded Hermes response from tests/fixtures/hermes."""

    def load(name: str) -> bytes:
        return (FIXTURES_DIR / name).read_bytes()

    return load


@pytest.fixture
def make_history() -> HistoryFactory:
    """Build a Hermes /history payload for EIN-AGP on 2026-12-10.

    Takes ``(observed_at, price)`` pairs, e.g. ``("2026-11-01T06:00:00Z", "99.99")``.
    """

    def build(points: Sequence[tuple[str, str]]) -> dict[str, object]:
        return {
            "origin": "EIN",
            "destination": "AGP",
            "tier": "guest",
            "window_start": "2026-08-27T00:00:00Z",
            "count": len(points),
            "has_more": False,
            "generated_at": "2026-11-25T12:00:00Z",
            "points": [
                {
                    "observed_at": observed_at,
                    "price": price,
                    "currency": "EUR",
                    "outbound_date": "2026-12-10",
                }
                for observed_at, price in points
            ],
        }

    return build


@pytest.fixture
def settings() -> Settings:
    return Settings(base_url=HERMES_URL, api_key=None, _env_file=None)


@pytest.fixture
def hermes() -> Iterator[respx.MockRouter]:
    """Mock Hermes at the HTTP level; any unmocked request fails the test."""
    with respx.mock(base_url=f"{HERMES_URL}/api/v1", assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def client(settings: Settings, hermes: respx.MockRouter) -> Iterator[TestClient]:
    """Test client for the real app, talking to the respx-mocked Hermes."""
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def fake_hermes() -> FakeHermesClient:
    return FakeHermesClient()


@pytest.fixture
def fake_client(
    settings: Settings, hermes: respx.MockRouter, fake_hermes: FakeHermesClient
) -> Iterator[TestClient]:
    """Test client whose Hermes client is replaced by ``fake_hermes``."""
    app = create_app(settings)
    app.dependency_overrides[get_hermes_client] = lambda: fake_hermes
    with TestClient(app) as test_client:
        yield test_client
