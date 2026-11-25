"""Scoring model answers against labels."""

from collections.abc import Sequence
from dataclasses import dataclass

from ftw.schema import FIELDS, Query, extract_json, validate_query


@dataclass(frozen=True)
class Scores:
    """Accuracy of a set of answers, as fractions between 0 and 1.

    Attributes:
        total: Number of scored examples.
        valid_json: Share of answers that parse as a JSON object.
        valid_schema: Share of answers that pass :func:`validate_query`.
        field_accuracy: Per field, the share of answers with the right value.
        exact_match: Share of answers with every field right.
    """

    total: int
    valid_json: float
    valid_schema: float
    field_accuracy: dict[str, float]
    exact_match: float

    @property
    def mean_field_accuracy(self) -> float:
        """Average of the per-field accuracies."""
        return sum(self.field_accuracy.values()) / len(self.field_accuracy)


def score(answers: Sequence[str], labels: Sequence[Query]) -> Scores:
    """Score raw model answers against their labels.

    An answer that is not valid JSON gets every field wrong.

    Args:
        answers: Raw model outputs.
        labels: The expected queries, in the same order.

    Returns:
        The aggregated scores.

    Raises:
        ValueError: If the inputs are empty or differ in length.
    """
    if not answers or len(answers) != len(labels):
        raise ValueError("need the same, non-zero number of answers and labels")
    parsed = [extract_json(answer) for answer in answers]
    correct = {field: 0 for field in FIELDS}
    exact = 0
    for prediction, label in zip(parsed, labels, strict=True):
        if prediction is None:
            continue
        hits = [prediction.get(field) == label[field] for field in FIELDS]
        for field, hit in zip(FIELDS, hits, strict=True):
            correct[field] += hit
        exact += all(hits)
    total = len(answers)
    valid = [prediction for prediction in parsed if prediction is not None]
    return Scores(
        total=total,
        valid_json=len(valid) / total,
        valid_schema=sum(not validate_query(p) for p in valid) / total,
        field_accuracy={field: hits / total for field, hits in correct.items()},
        exact_match=exact / total,
    )
