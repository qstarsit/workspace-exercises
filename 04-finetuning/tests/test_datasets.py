"""Checks on the shipped data sets, and on your training set.

Point FTW_TRAIN_DATA at your training file (default:
data/generated/train.jsonl) and run `uv run pytest tests/test_datasets.py`.
"""

import os
from pathlib import Path

import pytest

from ftw.data import (
    EVAL_PATH,
    SEED_PATH,
    Example,
    find_overlap,
    normalise_question,
    read_jsonl,
)
from ftw.schema import PROJECT_ROOT, validate_query

TRAIN_PATH = Path(
    os.environ.get("FTW_TRAIN_DATA", PROJECT_ROOT / "data/generated/train.jsonl")
)


def invalid_labels(examples: list[Example]) -> list[str]:
    return [
        f"{ex['question']!r}: {error}"
        for ex in examples
        for error in validate_query(ex["answer"])
    ]


def duplicates(examples: list[Example]) -> list[str]:
    seen: set[str] = set()
    repeated = []
    for ex in examples:
        question = normalise_question(ex["question"])
        if question in seen:
            repeated.append(question)
        seen.add(question)
    return repeated


@pytest.mark.parametrize("path", [SEED_PATH, EVAL_PATH], ids=["seed", "eval"])
def test_shipped_labels_are_valid_and_unique(path: Path) -> None:
    examples = read_jsonl(path)

    assert invalid_labels(examples) == []
    assert duplicates(examples) == []


def test_seed_does_not_leak_into_eval() -> None:
    assert find_overlap(read_jsonl(SEED_PATH), read_jsonl(EVAL_PATH)) == []


@pytest.mark.skipif(not TRAIN_PATH.is_file(), reason=f"no training set at {TRAIN_PATH}")
def test_training_set() -> None:
    train = read_jsonl(TRAIN_PATH)

    assert find_overlap(train, read_jsonl(EVAL_PATH)) == [], "eval questions leaked"
    assert invalid_labels(train) == []
    assert duplicates(train) == []
