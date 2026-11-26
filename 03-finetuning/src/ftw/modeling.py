"""Loading local models and generating answers with them."""

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

import orjson
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedTokenizerBase

from ftw.prompt import Message

DEFAULT_BASE_MODEL: Final = "HuggingFaceTB/SmolLM2-135M-Instruct"
RUN_CONFIG_NAME: Final = "ftw_run.json"
"""File in an adapter directory that records how the adapter was trained."""


def load_tokenizer(model_name: str) -> PreTrainedTokenizerBase:
    """Load a tokenizer that pads on the left, as batched generation needs.

    Args:
        model_name: Hugging Face model id or local path.

    Returns:
        The tokenizer.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def load_model(model_name: str, device: str = "cpu") -> torch.nn.Module:
    """Load a causal language model in float32.

    Args:
        model_name: Hugging Face model id or local path.
        device: Torch device, e.g. ``"cpu"``, ``"mps"`` or ``"cuda"``.

    Returns:
        The model on ``device``.
    """
    model: torch.nn.Module = AutoModelForCausalLM.from_pretrained(
        model_name, dtype=torch.float32
    )
    return model.to(device)


def read_run_config(adapter_dir: Path) -> dict[str, str]:
    """Read which base model and prompt style an adapter was trained with.

    Args:
        adapter_dir: Directory written by ``ftw.train``.

    Returns:
        The run configuration, with at least ``base_model`` and ``prompt``.
    """
    config: dict[str, str] = orjson.loads((adapter_dir / RUN_CONFIG_NAME).read_bytes())
    return config


def _batches[T](items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


@torch.inference_mode()
def generate(
    model: torch.nn.Module,
    tokenizer: PreTrainedTokenizerBase,
    chats: Sequence[list[Message]],
    batch_size: int = 16,
    max_new_tokens: int = 64,
) -> Iterator[list[str]]:
    """Answer chats greedily, a batch at a time.

    Args:
        model: Causal language model.
        tokenizer: Its tokenizer, padding on the left.
        chats: One message list per answer.
        batch_size: Chats per forward pass.
        max_new_tokens: Upper bound on answer length.

    Yields:
        The decoded answers of each batch, in input order.
    """
    device = next(model.parameters()).device
    for batch in _batches(chats, batch_size):
        prompts = [
            tokenizer.apply_chat_template(
                chat, tokenize=False, add_generation_prompt=True
            )
            for chat in batch
        ]
        encoded = tokenizer(
            prompts, return_tensors="pt", padding=True, add_special_tokens=False
        ).to(device)
        output = model.generate(  # type: ignore[operator]
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
        new_tokens = output[:, encoded["input_ids"].shape[1] :]
        yield tokenizer.batch_decode(new_tokens, skip_special_tokens=True)
