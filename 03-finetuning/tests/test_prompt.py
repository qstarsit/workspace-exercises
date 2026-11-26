import orjson

from ftw.prompt import FULL_SYSTEM_PROMPT, build_messages, format_answer
from ftw.schema import FIELDS, Query


def test_messages_have_system_and_user_turns() -> None:
    messages = build_messages("EIN to AGP tomorrow", "short")

    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"] == "EIN to AGP tomorrow"
    assert "2026-11-25" in messages[0]["content"]


def test_full_prompt_states_date_and_rules() -> None:
    system = build_messages("x")[0]["content"]

    assert system == FULL_SYSTEM_PROMPT
    assert "Wednesday 2026-11-25" in system
    for intent in ("cheapest_fare", "price_history", "deal_check", "explore"):
        assert intent in system


def test_answer_is_compact_json_in_schema_order() -> None:
    query: Query = {
        "date_to": "2026-12-01",
        "intent": "explore",
        "destination": None,
        "origin": "EIN",
        "date_from": "2026-11-30",
    }

    text = format_answer(query)

    assert " " not in text
    assert list(orjson.loads(text)) == list(FIELDS)
    assert '"destination":null' in text
