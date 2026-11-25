"""Prompts shared by evaluation, training and data generation."""

from typing import Final, Literal

import orjson

from ftw.schema import FIELDS, REFERENCE_DATE, Query

type PromptStyle = Literal["full", "short"]
type Message = dict[str, str]

TODAY: Final = f"Today is {REFERENCE_DATE:%A} {REFERENCE_DATE.isoformat()}."

FULL_SYSTEM_PROMPT: Final = f"""\
You turn questions about flight prices (English or Dutch) into a JSON query for a \
Ryanair fare database. {TODAY}

Reply with one JSON object on one line and nothing else:
{{"intent": ..., "origin": ..., "destination": ..., "date_from": ..., "date_to": ...}}

intent:
- "cheapest_fare": what a route costs, or its cheapest flight
- "price_history": how the price on a route has changed or is trending
- "deal_check": whether a given price on a route is a good deal
- "explore": where you can fly from an airport; destination is null
origin, destination: uppercase IATA codes of Ryanair airports; map cities to them.
date_from, date_to: the outbound travel dates as YYYY-MM-DD, both inclusive:
- one day: date_from = date_to
- a month: its first to last day; next year if the month has passed; from today \
if it is the current month
- early, mid, late in a month: days 1-10, 11-20, 21-last
- around a date: 3 days before to 3 days after
- this weekend: the coming Saturday and Sunday
- next week: Monday to Sunday of next week
- next month: all of next month
- the next N days or weeks: today to today + N days (or N * 7 days)
- a weekday: its first date after today
- Christmas: 24 to 26 December; New Year: 31 December to 1 January
- no date: today to today + 30 days"""

SHORT_SYSTEM_PROMPT: Final = f"{TODAY} Convert the flight question to JSON."

SYSTEM_PROMPTS: Final[dict[PromptStyle, str]] = {
    "full": FULL_SYSTEM_PROMPT,
    "short": SHORT_SYSTEM_PROMPT,
}


def build_messages(question: str, style: PromptStyle = "full") -> list[Message]:
    """Build the chat messages that ask a model to answer one question.

    Args:
        question: The user's free-text flight question.
        style: ``"full"`` spells out every rule (for models that were not
            trained on this task); ``"short"`` only states today's date.

    Returns:
        A system and a user message.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPTS[style]},
        {"role": "user", "content": question},
    ]


def format_answer(query: Query) -> str:
    """Serialise a query as the exact answer a model should produce.

    Args:
        query: A valid query.

    Returns:
        Compact JSON with the keys in schema order.
    """
    return orjson.dumps({field: query[field] for field in FIELDS}).decode()
