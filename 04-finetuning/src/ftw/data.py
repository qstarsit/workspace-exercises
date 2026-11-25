"""Reading and writing labelled examples, and checking for train/eval overlap."""

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final, TypedDict

import orjson

from ftw.schema import DATA_DIR, Query

EVAL_PATH: Final = DATA_DIR / "eval.jsonl"
SEED_PATH: Final = DATA_DIR / "seed.jsonl"

_NON_WORD = re.compile(r"[\W_]+")


class Example(TypedDict):
    """One labelled example: a question and the query it should produce."""

    question: str
    answer: Query


def read_jsonl(path: Path) -> list[Example]:
    """Read examples from a JSON Lines file, skipping blank lines.

    Args:
        path: File with one JSON object per line.

    Returns:
        The examples in file order.
    """
    with path.open("rb") as handle:
        return [orjson.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, examples: Iterable[Example]) -> None:
    """Write examples to a JSON Lines file, creating parent directories.

    Args:
        path: Destination file; overwritten if it exists.
        examples: Examples to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.writelines(
            orjson.dumps(example, option=orjson.OPT_APPEND_NEWLINE)
            for example in examples
        )


def normalise_question(question: str) -> str:
    """Reduce a question to lowercase words, for duplicate detection.

    Args:
        question: Free-text question.

    Returns:
        The question without case, punctuation or repeated whitespace.

    Example:
        >>> normalise_question("Cheap flights, EIN -> AGP?")
        'cheap flights ein agp'
    """
    return _NON_WORD.sub(" ", question.lower()).strip()


def find_overlap(train: Iterable[Example], held_out: Iterable[Example]) -> list[str]:
    """Find training questions that also occur in a held-out set.

    Questions are compared after :func:`normalise_question`, so a copy with
    different casing or punctuation still counts as leakage.

    Args:
        train: Training examples.
        held_out: Evaluation examples.

    Returns:
        The overlapping normalised questions, sorted.
    """
    held_out_questions = {normalise_question(ex["question"]) for ex in held_out}
    return sorted(
        {normalise_question(ex["question"]) for ex in train} & held_out_questions
    )
