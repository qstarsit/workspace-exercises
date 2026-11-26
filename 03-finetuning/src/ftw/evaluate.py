"""Evaluate a local model, a LoRA adapter or a Bedrock model on the eval set.

Examples:
    uv run python -m ftw.evaluate                          # untuned base model
    uv run python -m ftw.evaluate --adapter adapters/run1  # fine-tuned adapter
    uv run python -m ftw.evaluate --bedrock zai.glm-5      # the teacher
"""

import argparse
import logging
import statistics
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import orjson
from peft import PeftModel
from tqdm import tqdm

from ftw import bedrock, configure_logging
from ftw.data import EVAL_PATH, Example, read_jsonl
from ftw.metrics import Scores, score
from ftw.modeling import (
    DEFAULT_BASE_MODEL,
    generate,
    load_model,
    load_tokenizer,
    read_run_config,
)
from ftw.prompt import Message, PromptStyle, build_messages
from ftw.schema import FIELDS, extract_json

logger = logging.getLogger("ftw.evaluate")


@dataclass(frozen=True)
class Run:
    """Answers of one model on the eval set, with timing and usage.

    Attributes:
        name: Label for the scoreboard.
        answers: Raw model outputs, in eval order.
        seconds: Wall-clock time spent answering.
        latencies: Per-call latencies (Bedrock only).
        input_tokens: Billed input tokens (Bedrock only).
        output_tokens: Billed output tokens (Bedrock only).
        cost_usd: Estimated cost (Bedrock only).
    """

    name: str
    answers: list[str]
    seconds: float
    latencies: tuple[float, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


def run_local(
    model_name: str,
    adapter: Path | None,
    chats: Sequence[list[Message]],
    device: str,
    batch_size: int,
) -> Run:
    """Answer every chat with a local model, optionally with a LoRA adapter.

    Args:
        model_name: Base model id or path.
        adapter: Adapter directory from ``ftw.train``, merged into the model.
        chats: One message list per eval example.
        device: Torch device.
        batch_size: Chats per generation batch.

    Returns:
        The answers and timing.
    """
    tokenizer = load_tokenizer(model_name)
    model = load_model(model_name, device)
    if adapter is not None:
        model = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    model.eval()
    answers: list[str] = []
    started = time.perf_counter()
    with tqdm(total=len(chats), desc="Answering eval questions", unit="q") as bar:
        for batch in generate(model, tokenizer, chats, batch_size):
            answers.extend(batch)
            bar.update(len(batch))
    name = str(adapter) if adapter is not None else model_name
    return Run(name, answers, time.perf_counter() - started)


def run_bedrock(model_id: str, chats: Sequence[list[Message]], workers: int) -> Run:
    """Answer every chat with a Bedrock model, several calls at a time.

    Args:
        model_id: Bedrock model id.
        chats: One message list per eval example.
        workers: Concurrent calls.

    Returns:
        The answers, timing, token usage and cost estimate.
    """
    client = bedrock.make_client(workers)
    started = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        replies = list(
            tqdm(
                pool.map(lambda chat: bedrock.converse(client, chat, model_id), chats),
                total=len(chats),
                desc=f"Asking {model_id}",
                unit="q",
            )
        )
    seconds = time.perf_counter() - started
    input_tokens = sum(reply.input_tokens for reply in replies)
    output_tokens = sum(reply.output_tokens for reply in replies)
    return Run(
        name=model_id,
        answers=[reply.text for reply in replies],
        seconds=seconds,
        latencies=tuple(reply.latency_seconds for reply in replies),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=bedrock.cost_usd(model_id, input_tokens, output_tokens),
    )


def write_predictions(
    path: Path, examples: Sequence[Example], answers: list[str]
) -> None:
    """Write each question, label and answer, for error analysis.

    Args:
        path: Destination JSON Lines file.
        examples: Eval examples.
        answers: Raw model answers, in the same order.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for example, answer in zip(examples, answers, strict=True):
            parsed = extract_json(answer)
            wrong = [
                field
                for field in FIELDS
                if parsed is None or parsed.get(field) != example["answer"][field]
            ]
            record = {**example, "raw": answer, "wrong_fields": wrong}
            handle.write(orjson.dumps(record, option=orjson.OPT_APPEND_NEWLINE))


def report(run: Run, scores: Scores, style: str) -> str:
    """Format the scores of a run as a short report and a scoreboard row.

    Args:
        run: The evaluated run.
        scores: Its scores.
        style: Prompt style used.

    Returns:
        Multi-line text for the console.
    """
    per_question_ms = run.seconds / scores.total * 1000
    per_1000 = None if run.cost_usd is None else run.cost_usd / scores.total * 1000
    lines = [
        f"model            {run.name} ({style} prompt)",
        f"examples         {scores.total}",
        f"valid JSON       {scores.valid_json:.1%}",
        f"valid schema     {scores.valid_schema:.1%}",
        *(
            f"  {field:<14} {accuracy:.1%}"
            for field, accuracy in scores.field_accuracy.items()
        ),
        f"field accuracy   {scores.mean_field_accuracy:.1%}",
        f"exact match      {scores.exact_match:.1%}",
        f"throughput       {scores.total / run.seconds:.2f} q/s "
        f"({per_question_ms:.0f} ms per question, {run.seconds:.0f} s total)",
    ]
    if run.latencies:
        p95 = statistics.quantiles(run.latencies, n=20)[18]
        lines.append(
            f"latency per call p50 {statistics.median(run.latencies):.2f} s, "
            f"p95 {p95:.2f} s"
        )
        lines.append(
            f"tokens           {run.input_tokens} in, {run.output_tokens} out, "
            + ("price unknown" if per_1000 is None else f"${per_1000:.2f} per 1000 q")
        )
    cost = "" if per_1000 is None else f"${per_1000:.2f}/1k q"
    lines.append(
        f"scoreboard row   | {run.name} | | | {scores.valid_json:.0%} "
        f"| {scores.mean_field_accuracy:.1%} | {scores.exact_match:.1%} "
        f"| {scores.total / run.seconds:.2f} q/s | {cost} |"
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--model", default=DEFAULT_BASE_MODEL, help="local base model")
    source.add_argument("--adapter", type=Path, help="LoRA adapter dir from ftw.train")
    source.add_argument("--bedrock", metavar="MODEL_ID", help="e.g. zai.glm-5")
    parser.add_argument("--data", type=Path, default=EVAL_PATH)
    parser.add_argument("--limit", type=int, help="only the first N examples")
    parser.add_argument(
        "--prompt",
        choices=["full", "short"],
        help="prompt style; default: the adapter's training style, else full",
    )
    parser.add_argument("--device", default="cpu", help="cpu, mps or cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=8, help="Bedrock concurrency")
    parser.add_argument(
        "--output", type=Path, help="predictions file (default: outputs/<model>.jsonl)"
    )
    return parser.parse_args()


def main() -> None:
    """Run the evaluation from the command line."""
    configure_logging()
    args = parse_args()
    examples = read_jsonl(args.data)[: args.limit]
    model_name: str = args.model
    style: str = args.prompt or "full"
    if args.adapter is not None:
        run_config = read_run_config(args.adapter)
        model_name = run_config["base_model"]
        style = args.prompt or run_config["prompt"]
    chats = [
        build_messages(ex["question"], cast(PromptStyle, style)) for ex in examples
    ]
    if args.bedrock is not None:
        run = run_bedrock(args.bedrock, chats, args.workers)
    else:
        run = run_local(model_name, args.adapter, chats, args.device, args.batch_size)
    scores = score(run.answers, [ex["answer"] for ex in examples])
    output = args.output or Path("outputs") / f"{Path(run.name).name}.jsonl"
    write_predictions(output, examples, run.answers)
    logger.info("%s\npredictions      %s", report(run, scores, style), output)


if __name__ == "__main__":
    main()
