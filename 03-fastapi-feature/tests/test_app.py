import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from fare_watch.config import Settings
from fare_watch.main import create_app


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_key_is_sent_when_configured(
    settings: Settings, hermes: respx.MockRouter
) -> None:
    route = hermes.get("/airports/").respond(200, json={"items": []})
    app = create_app(settings.model_copy(update={"api_key": SecretStr("s3cret")}))

    with TestClient(app) as client:
        client.get("/airports")

    assert route.calls.last.request.headers["X-API-Key"] == "s3cret"


def test_no_api_key_header_for_guest_access(
    client: TestClient, hermes: respx.MockRouter
) -> None:
    route = hermes.get("/airports/").respond(200, json={"items": []})

    client.get("/airports")

    assert "X-API-Key" not in route.calls.last.request.headers
