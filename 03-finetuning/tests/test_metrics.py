import orjson
import pytest

from ftw.metrics import score
from ftw.schema import Query

LABEL: Query = {
    "intent": "cheapest_fare",
    "origin": "EIN",
    "destination": "AGP",
    "date_from": "2026-12-10",
    "date_to": "2026-12-20",
}


def answer(**overrides: str | None) -> str:
    return orjson.dumps({**LABEL, **overrides}).decode()


def test_perfect_answers() -> None:
    scores = score([answer(), answer()], [LABEL, LABEL])

    assert scores.valid_json == 1.0
    assert scores.valid_schema == 1.0
    assert scores.exact_match == 1.0
    assert scores.mean_field_accuracy == 1.0


def test_one_wrong_field_counts_per_field_but_not_exact() -> None:
    scores = score([answer(), answer(destination="ALC")], [LABEL, LABEL])

    assert scores.exact_match == 0.5
    assert scores.field_accuracy["destination"] == 0.5
    assert scores.field_accuracy["origin"] == 1.0
    assert scores.mean_field_accuracy == pytest.approx(0.9)


def test_invalid_json_gets_every_field_wrong() -> None:
    scores = score(["not json", answer()], [LABEL, LABEL])

    assert scores.valid_json == 0.5
    assert scores.exact_match == 0.5
    assert all(accuracy == 0.5 for accuracy in scores.field_accuracy.values())


def test_valid_json_with_bad_schema() -> None:
    scores = score([answer(origin="XXX"), '{"intent": "explore"}'], [LABEL, LABEL])

    assert scores.valid_json == 1.0
    assert scores.valid_schema == 0.0
    assert scores.field_accuracy["intent"] == 0.5


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError, match="same"):
        score([answer()], [LABEL, LABEL])
    with pytest.raises(ValueError, match="same"):
        score([], [])
