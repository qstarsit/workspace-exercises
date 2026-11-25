from fastapi.testclient import TestClient

from fare_watch.domain import Airport
from tests.support import FakeHermesClient

EINDHOVEN = Airport("EIN", "Eindhoven", "nl", "Europe/Amsterdam", is_base=True)
AMSTERDAM = Airport("AMS", "Amsterdam", "nl", "Europe/Amsterdam", is_base=False)
MALAGA = Airport("AGP", "Malaga", "es", "Europe/Madrid", is_base=True)


def test_list_airports_sorted_by_iata(
    fake_client: TestClient, fake_hermes: FakeHermesClient
) -> None:
    fake_hermes.airports = [EINDHOVEN, MALAGA, AMSTERDAM]

    response = fake_client.get("/airports")

    assert response.status_code == 200
    assert [airport["iata"] for airport in response.json()] == ["AGP", "AMS", "EIN"]
    assert response.json()[2] == {
        "iata": "EIN",
        "name": "Eindhoven",
        "country_code": "nl",
        "time_zone": "Europe/Amsterdam",
        "is_base": True,
    }


def test_list_airports_filters_by_country_case_insensitively(
    fake_client: TestClient, fake_hermes: FakeHermesClient
) -> None:
    fake_hermes.airports = [EINDHOVEN, MALAGA, AMSTERDAM]

    response = fake_client.get("/airports", params={"country": "NL"})

    assert [airport["iata"] for airport in response.json()] == ["AMS", "EIN"]


def test_list_airports_rejects_invalid_country(fake_client: TestClient) -> None:
    response = fake_client.get("/airports", params={"country": "NLD"})

    assert response.status_code == 422
