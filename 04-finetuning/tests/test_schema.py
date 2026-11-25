import pytest

from ftw.schema import (
    REFERENCE_DATE,
    Query,
    extract_json,
    load_airports,
    validate_query,
)

AIRPORTS = frozenset({"EIN", "AGP", "DUB"})


def valid_query(**overrides: str | None) -> Query:
    query: Query = {
        "intent": "cheapest_fare",
        "origin": "EIN",
        "destination": "AGP",
        "date_from": "2026-12-10",
        "date_to": "2026-12-20",
    }
    return {**query, **overrides}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": "x"}', {"a": "x"}),
        ('  {"a": "x"}\n', {"a": "x"}),
        ('```json\n{"a": "x"}\n```', {"a": "x"}),
        ('```\n{"a": "x"}\n```', {"a": "x"}),
        ('Sure! {"a": "x"}', None),
        ('{"a": "x"', None),
        ("[1, 2]", None),
        ("", None),
    ],
)
def test_extract_json(text: str, expected: Query | None) -> None:
    assert extract_json(text) == expected


def test_valid_query_has_no_errors() -> None:
    assert validate_query(valid_query(), AIRPORTS) == []


def test_explore_needs_null_destination() -> None:
    explore = valid_query(intent="explore", destination=None)

    assert validate_query(explore, AIRPORTS) == []
    assert validate_query(valid_query(intent="explore"), AIRPORTS)
    assert validate_query(valid_query(destination=None), AIRPORTS)


@pytest.mark.parametrize(
    "overrides",
    [
        {"intent": "book_flight"},
        {"origin": "RTM"},
        {"origin": "ein"},
        {"destination": "EIN"},
        {"date_from": "10-12-2026"},
        {"date_to": "2026-12-32"},
        {"date_from": "2026-12-21"},
        {"date_from": "2026-11-24", "date_to": "2026-11-24"},
    ],
)
def test_invalid_values_are_reported(overrides: dict[str, str]) -> None:
    assert validate_query(valid_query(**overrides), AIRPORTS)


def test_missing_and_extra_keys_are_reported() -> None:
    missing = {k: v for k, v in valid_query().items() if k != "date_to"}

    assert validate_query(missing, AIRPORTS)
    assert validate_query({**valid_query(), "price": "39"}, AIRPORTS)


def test_reference_date_is_fixed() -> None:
    assert REFERENCE_DATE.isoformat() == "2026-11-25"


def test_airport_snapshot_holds_ryanair_airports() -> None:
    airports = load_airports()

    assert {"EIN", "CRL", "STN", "AGP"} <= airports
    assert "RTM" not in airports
