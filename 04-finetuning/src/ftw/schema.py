"""The structured query a model must produce, and how to parse and validate it."""

from datetime import date
from functools import cache
from pathlib import Path
from typing import Final

import orjson

PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
DATA_DIR: Final = PROJECT_ROOT / "data"
AIRPORTS_PATH: Final = DATA_DIR / "airports.json"

REFERENCE_DATE: Final = date(2026, 11, 25)
"""The "today" every prompt states, so relative dates have one right answer."""

INTENTS: Final = frozenset({"cheapest_fare", "price_history", "deal_check", "explore"})
FIELDS: Final = ("intent", "origin", "destination", "date_from", "date_to")

type Query = dict[str, str | None]


@cache
def load_airports(path: Path = AIRPORTS_PATH) -> frozenset[str]:
    """Load the IATA codes of all Ryanair airports known to Hermes.

    The file is a snapshot of ``GET /api/v1/airports/?limit=1000`` on Hermes.

    Args:
        path: JSON file with a list of airport objects that have an ``iata`` key.

    Returns:
        The set of valid IATA codes.
    """
    return frozenset(airport["iata"] for airport in orjson.loads(path.read_bytes()))


def extract_json(text: str) -> Query | None:
    """Parse a model answer into a JSON object.

    The whole answer must be one JSON object; surrounding whitespace and a
    Markdown code fence are tolerated, any other text is not.

    Args:
        text: Raw model output.

    Returns:
        The parsed object, or ``None`` if the answer is not a JSON object.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```")
        stripped = stripped.removesuffix("```").strip()
    try:
        parsed = orjson.loads(stripped)
    except orjson.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value) if len(value) == 10 else None
    except ValueError:
        return None


def validate_query(query: Query, airports: frozenset[str] | None = None) -> list[str]:
    """Check a query against the schema and the business rules.

    Args:
        query: A parsed model answer or label.
        airports: Valid IATA codes. Defaults to the Hermes snapshot.

    Returns:
        Human-readable problems; empty if the query is valid.
    """
    valid_codes = load_airports() if airports is None else airports
    errors: list[str] = []
    if sorted(query) != sorted(FIELDS):
        errors.append(f"keys must be exactly {list(FIELDS)}, got {sorted(query)}")
    intent = query.get("intent")
    if intent not in INTENTS:
        errors.append(f"unknown intent {intent!r}")
    origin = query.get("origin")
    if origin not in valid_codes:
        errors.append(f"origin {origin!r} is not a Ryanair airport")
    destination = query.get("destination")
    if intent == "explore":
        if destination is not None:
            errors.append("destination must be null for explore")
    elif destination not in valid_codes:
        errors.append(f"destination {destination!r} is not a Ryanair airport")
    elif destination == origin:
        errors.append("destination equals origin")
    date_from = _parse_date(query.get("date_from"))
    date_to = _parse_date(query.get("date_to"))
    if date_from is None or date_to is None:
        errors.append("date_from and date_to must be YYYY-MM-DD")
    elif date_from > date_to:
        errors.append("date_from is after date_to")
    elif date_from < REFERENCE_DATE:
        errors.append(f"date_from is before today ({REFERENCE_DATE})")
    return errors
