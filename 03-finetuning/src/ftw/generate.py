"""Ask the teacher model for new labelled examples (a starting point only).

One call, no validation: every line that parses as JSON is appended to the
output file as-is. Checking and cleaning the result is up to you.

Example:
    uv run python -m ftw.generate --n 20 --output data/generated/raw.jsonl
"""

import argparse
import logging
import random
from pathlib import Path

import orjson

from ftw import bedrock, configure_logging
from ftw.data import SEED_PATH, read_jsonl
from ftw.prompt import FULL_SYSTEM_PROMPT

logger = logging.getLogger("ftw.generate")

GENERATOR_PROMPT = f"""\
You write training data for a model with these instructions:

<instructions>
{FULL_SYSTEM_PROMPT}
</instructions>

Write new, varied questions that real users could type, each with the correct
answer. Output JSON Lines only: one object per line with the keys "question"
and "answer", like the examples."""


def main() -> None:
    """Generate examples from the command line."""
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=20, help="examples to ask for")
    parser.add_argument("--shots", type=int, default=8, help="seed examples shown")
    parser.add_argument("--model", default=bedrock.DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=Path("data/generated/raw.jsonl"))
    args = parser.parse_args()

    shots = random.sample(read_jsonl(SEED_PATH), args.shots)
    examples = "\n".join(orjson.dumps(ex).decode() for ex in shots)
    reply = bedrock.converse(
        bedrock.make_client(),
        [
            {"role": "system", "content": GENERATOR_PROMPT},
            {
                "role": "user",
                "content": f"Examples:\n{examples}\n\nWrite {args.n} more.",
            },
        ],
        model_id=args.model,
        max_tokens=150 * args.n,
        temperature=1.0,
    )

    lines = [line.strip() for line in reply.text.splitlines() if line.strip()]
    parsed = []
    for line in lines:
        try:
            parsed.append(orjson.loads(line))
        except orjson.JSONDecodeError:
            logger.warning("Skipping a line that is not JSON: %.80s", line)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("ab") as handle:
        handle.writelines(
            orjson.dumps(item, option=orjson.OPT_APPEND_NEWLINE) for item in parsed
        )
    logger.info(
        "Appended %d examples to %s (%d in, %d out tokens, %.0f s)",
        len(parsed),
        args.output,
        reply.input_tokens,
        reply.output_tokens,
        reply.latency_seconds,
    )


if __name__ == "__main__":
    main()
