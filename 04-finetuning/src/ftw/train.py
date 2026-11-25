"""Fine-tune a small model with LoRA on labelled flight questions.

Example:
    uv run python -m ftw.train --data data/generated/train.jsonl --output adapters/run1
"""

import argparse
import logging
import random
import time
from pathlib import Path

import orjson
import torch
from peft import LoraConfig, get_peft_model
from tqdm import tqdm
from transformers import PreTrainedTokenizerBase, get_linear_schedule_with_warmup

from ftw import configure_logging
from ftw.data import Example, read_jsonl
from ftw.modeling import DEFAULT_BASE_MODEL, RUN_CONFIG_NAME, load_model, load_tokenizer
from ftw.prompt import PromptStyle, build_messages, format_answer

logger = logging.getLogger("ftw.train")


def tokenize_examples(
    examples: list[Example],
    tokenizer: PreTrainedTokenizerBase,
    style: PromptStyle,
    max_length: int,
) -> list[list[int]]:
    """Render each example as a full chat and tokenize it.

    Args:
        examples: Labelled examples.
        tokenizer: Tokenizer with a chat template.
        style: Prompt style the model will be asked with later.
        max_length: Longer sequences are truncated.

    Returns:
        Token ids per example.
    """
    texts = [
        tokenizer.apply_chat_template(
            [
                *build_messages(ex["question"], style),
                {"role": "assistant", "content": format_answer(ex["answer"])},
            ],
            tokenize=False,
        )
        for ex in examples
    ]
    encoded = tokenizer(
        texts, add_special_tokens=False, truncation=True, max_length=max_length
    )
    ids: list[list[int]] = encoded["input_ids"]
    return ids


def collate(sequences: list[list[int]], pad_id: int) -> dict[str, torch.Tensor]:
    """Right-pad a batch and mask the padding out of the loss.

    Args:
        sequences: Token ids per example.
        pad_id: Padding token id.

    Returns:
        ``input_ids``, ``attention_mask`` and ``labels`` tensors.
    """
    width = max(map(len, sequences))
    input_ids = torch.full((len(sequences), width), pad_id)
    attention_mask = torch.zeros((len(sequences), width), dtype=torch.long)
    for row, sequence in enumerate(sequences):
        input_ids[row, : len(sequence)] = torch.tensor(sequence)
        attention_mask[row, : len(sequence)] = 1
    labels = input_ids.masked_fill(attention_mask == 0, -100)
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="training JSONL")
    parser.add_argument("--output", type=Path, required=True, help="adapter directory")
    parser.add_argument("--model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--rank", type=int, default=16, help="LoRA rank")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256, help="tokens")
    parser.add_argument("--prompt", choices=["full", "short"], default="short")
    parser.add_argument("--device", default="cpu", help="cpu, mps or cuda")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--max-examples",
        type=int,
        default=600,
        help="train on a random sample of at most this many examples "
        "(600 keeps a run around 10-12 min on 5 CPUs; 0 = use all)",
    )
    return parser.parse_args()


def sample_examples[T](examples: list[T], limit: int, seed: int) -> list[T]:
    """Pick a reproducible random sample of training examples.

    Args:
        examples: All training examples.
        limit: Maximum number to keep; 0 or less keeps all of them.
        seed: Random seed, so the same flags give the same sample.

    Returns:
        At most ``limit`` examples, in random order.
    """
    if limit <= 0 or len(examples) <= limit:
        return examples
    return random.Random(seed).sample(examples, limit)


def main() -> None:
    """Train a LoRA adapter from the command line."""
    configure_logging()
    args = parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    tokenizer = load_tokenizer(args.model)
    examples = sample_examples(read_jsonl(args.data), args.max_examples, args.seed)
    sequences = tokenize_examples(examples, tokenizer, args.prompt, args.max_length)
    logger.info(
        "%d examples, %.0f tokens on average",
        len(sequences),
        sum(map(len, sequences)) / len(sequences),
    )

    model = get_peft_model(
        load_model(args.model, args.device),
        LoraConfig(
            r=args.rank,
            lora_alpha=2 * args.rank,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    steps_per_epoch = -(-len(sequences) // args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.lr
    )
    scheduler = get_linear_schedule_with_warmup(  # type: ignore[no-untyped-call]
        optimizer, num_warmup_steps=total_steps // 20, num_training_steps=total_steps
    )

    model.train()
    started = time.perf_counter()
    with tqdm(total=total_steps, desc="Training LoRA adapter", unit="step") as bar:
        for epoch in range(args.epochs):
            order = random.sample(range(len(sequences)), len(sequences))
            for start in range(0, len(order), args.batch_size):
                batch = collate(
                    [sequences[i] for i in order[start : start + args.batch_size]],
                    tokenizer.pad_token_id,
                )
                loss = model(**{k: v.to(args.device) for k, v in batch.items()}).loss
                loss.backward()
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                bar.set_postfix(epoch=epoch + 1, loss=f"{loss.item():.3f}")
                bar.update()
    minutes = (time.perf_counter() - started) / 60

    model.save_pretrained(args.output)
    run_config = {
        "base_model": args.model,
        "prompt": args.prompt,
        "data": str(args.data),
        "examples": len(sequences),
        "epochs": args.epochs,
        "lr": args.lr,
        "rank": args.rank,
        "batch_size": args.batch_size,
        "max_length": args.max_length,
        "train_minutes": round(minutes, 1),
    }
    (args.output / RUN_CONFIG_NAME).write_bytes(
        orjson.dumps(run_config, option=orjson.OPT_INDENT_2)
    )
    logger.info("Trained in %.1f min, adapter saved to %s", minutes, args.output)


if __name__ == "__main__":
    main()
