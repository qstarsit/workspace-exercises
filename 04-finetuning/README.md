# Exercise 4: distil GLM-5 into a tiny local model

GLM-5 on Bedrock turns free-text flight questions into a structured query almost perfectly, but every call costs money and about a second. Fine-tune a 135M-parameter model on your CPU to do the same job.

Every question becomes one JSON object:

```json
{"intent": "cheapest_fare", "origin": "EIN", "destination": "AGP", "date_from": "2026-12-11", "date_to": "2026-12-20"}
```

The rules (intents, airports, dates relative to a fixed today of 2026-11-25) are in `FULL_SYSTEM_PROMPT` in `src/ftw/prompt.py`.

## Setup

Give the Podman VM 8 GB of memory. In the dev container:

```bash
uv sync
uv run python -m ftw.download
uv run pytest
```

`data/raw/glm5_raw.jsonl` holds 998 unchecked examples written by GLM-5. Never train on `data/eval.jsonl`.

## Tasks

1. **Baseline.** Score the untuned model (`uv run python -m ftw.evaluate`) and the teacher (`--bedrock zai.glm-5`) in the scoreboard.
2. **Training data.** Build `data/generated/train.jsonl`. Done when `FTW_TRAIN_DATA=data/generated/train.jsonl uv run pytest tests/test_datasets.py` passes. `ftw.generate` makes more; 1,000 examples cost about $0.30.
3. **Fine-tune.** `uv run python -m ftw.train --data data/generated/train.jsonl --output adapters/run1`, then `ftw.evaluate --adapter adapters/run1`. A run takes about 14 minutes; no run may take longer than 20. Done when an adapter scores at least **85% field accuracy, 55% exact match and 100% valid JSON**.

## Scoreboard

| Model | Training data | Settings | Valid JSON | Field acc. | Exact | Throughput |
|---|---|---|---|---|---|---|
| SmolLM2-135M, untuned | | | | | | |
| GLM-5 (Bedrock) | | | | | | |
| run 1 | | | | | | |
| run 2 | | | | | | |
| run 3 | | | | | | |
