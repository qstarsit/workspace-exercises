from pathlib import Path

from ftw.data import Example, find_overlap, normalise_question, read_jsonl, write_jsonl


def example(question: str) -> Example:
    return {
        "question": question,
        "answer": {
            "intent": "explore",
            "origin": "EIN",
            "destination": None,
            "date_from": "2026-11-25",
            "date_to": "2026-12-25",
        },
    }


def test_normalise_ignores_case_punctuation_and_spacing() -> None:
    assert (
        normalise_question("  Cheap  flights, EIN -> AGP?") == "cheap flights ein agp"
    )


def test_overlap_finds_near_copies() -> None:
    train = [example("Where can I fly from Eindhoven?"), example("something else")]
    held_out = [example("where can i fly from eindhoven")]

    assert find_overlap(train, held_out) == ["where can i fly from eindhoven"]


def test_no_overlap() -> None:
    assert find_overlap([example("a")], [example("b")]) == []


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "data.jsonl"
    examples = [example("one"), example("twee")]

    write_jsonl(path, examples)

    assert read_jsonl(path) == examples
