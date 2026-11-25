# Exercise 4: distil GLM-5 into a tiny local model

GLM-5 on Bedrock turns free-text flight questions into a structured query almost perfectly, but every call costs money and about a second. Make a 135M-parameter model, fine-tuned on your laptop's CPU, do the same job well enough to replace it.

## The output contract

Every question becomes one JSON object:

```json
{"intent": "cheapest_fare", "origin": "EIN", "destination": "AGP", "date_from": "2026-12-11", "date_to": "2026-12-20"}
```

- `intent`: `cheapest_fare`, `price_history`, `deal_check` or `explore`.
- `origin`, `destination`: IATA codes of Ryanair airports (`data/airports.json`, from Hermes). `destination` is `null` only for `explore`.
- `date_from`, `date_to`: outbound travel dates, relative to a fixed today: Wednesday 2026-11-25. The full rules are in `FULL_SYSTEM_PROMPT` in `src/ftw/prompt.py`.

## Time budget

About 90 minutes. A training run takes about 14 minutes on 5 CPUs and an evaluation under a minute, so you get **three training runs**. No single run may take longer than 20 minutes.

## Setup

Give the Podman VM 8 GB of memory (6 GB minimum). In the dev container:

```bash
uv sync
uv run python -m ftw.download
uv run pytest            # passes, without network access
```

```
data/seed.jsonl           42 labelled examples
data/eval.jsonl           122 held-out examples: never train on these
data/raw/glm5_raw.jsonl   998 examples written by GLM-5, unchecked
src/ftw/                  evaluate, train, generate, schema and prompt code
```

## Tasks

### 1. Baseline

Score the untuned model and the teacher, and put both in the scoreboard:

```bash
uv run python -m ftw.evaluate
uv run python -m ftw.evaluate --bedrock zai.glm-5
```

### 2. Training data

Build `data/generated/train.jsonl` from the raw GLM-5 examples (and more if you need them).

Acceptance: `FTW_TRAIN_DATA=data/generated/train.jsonl uv run pytest tests/test_datasets.py` passes.

To generate more, `uv run python -m ftw.generate --n 20 --output data/generated/extra.jsonl` makes one call. About 1,000 generated examples cost roughly $0.30.

### 3. Fine-tune

```bash
uv run python -m ftw.train --data data/generated/train.jsonl --output adapters/run1
uv run python -m ftw.evaluate --adapter adapters/run1
```

`train.py` uses at most 600 examples per run (`--max-examples`). Every command takes `--help`.

Acceptance: an adapter that scores at least **85% field accuracy, 55% exact match and 100% valid JSON** on `eval.jsonl`.

## Scoreboard

| Model | Training data | Settings | Valid JSON | Field acc. | Exact | Throughput | Cost / 1k q |
|---|---|---|---|---|---|---|---|
| SmolLM2-135M, untuned | | | | | | | |
| GLM-5 (Bedrock) | | | | | | | |
| SmolLM2-135M + LoRA, run 1 | | | | | | | |
| run 2 | | | | | | | |
| run 3 | | | | | | | |

## Done when

- Your training set passes `tests/test_datasets.py`.
- One adapter meets the target, trained in at most 20 minutes, and the scoreboard is filled in.

## Stretch goals

- Train `HuggingFaceTB/SmolLM2-360M-Instruct` (`--model`) and compare.
- Constrain decoding to the JSON schema or the airport list.
- Quantise the merged model and measure speed against accuracy.

## Questions

- How would you know if eval questions leaked into training, and what would that do to what the score means?
- Does doubling the synthetic data double the improvement? Where does it stop helping?
- Can the student ever be better than its teacher? Where are their errors the same?
- What happens to this model on 26 November? What would you change for production?
- When is fine-tuning a small model better than prompting a large one, and when is it not worth it?
