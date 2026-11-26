import torch

from ftw.train import collate, sample_examples


def test_collate_pads_right_and_masks_padding() -> None:
    batch = collate([[5, 6, 7], [8]], pad_id=0)

    assert batch["input_ids"].tolist() == [[5, 6, 7], [8, 0, 0]]
    assert batch["attention_mask"].tolist() == [[1, 1, 1], [1, 0, 0]]
    assert batch["labels"].tolist() == [[5, 6, 7], [8, -100, -100]]
    assert batch["labels"].dtype == torch.long


def test_sample_examples_is_reproducible_and_capped() -> None:
    examples = list(range(10))

    first = sample_examples(examples, 4, seed=1)

    assert len(first) == 4
    assert first == sample_examples(examples, 4, seed=1)
    assert set(first) <= set(examples)


def test_sample_examples_keeps_everything_when_limit_is_off_or_large() -> None:
    examples = list(range(5))

    assert sample_examples(examples, 0, seed=1) == examples
    assert sample_examples(examples, 50, seed=1) == examples
