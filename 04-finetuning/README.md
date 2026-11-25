# Exercise 4: distil GLM-5 into a tiny local model

Fare Watch (exercise 3) wants a search box where people type a flight question in plain English or Dutch. Before it can call Hermes, the question has to become a structured query:

```
"cheapest flight eindhoven to malaga mid december"
```

```json
{"intent": "cheapest_fare", "origin": "EIN", "destination": "AGP", "date_from": "2026-12-11", "date_to": "2026-12-20"}
```

GLM-5 on Bedrock does this almost perfectly, but every question costs money and takes about a second. A small model running locally would be free and fast, but out of the box it cannot do the job.

In this exercise you distil GLM-5 into SmolLM2-135M: GLM-5 is the teacher that writes labelled examples, and you fine-tune the small model (LoRA, on your CPU) on those examples until it is nearly as accurate. You measure both models on the same held-out questions, so you can decide whether the small one is good enough to replace GLM-5.

The output rules (the four intents, which airports exist, and how dates are resolved against a fixed today of Wednesday 2026-11-25) are in `FULL_SYSTEM_PROMPT` in `src/ftw/prompt.py`.

## Bedrock

Everything is preset for the workshop: the endpoint is `https://bedrock-runtime.eu-north-1.amazonaws.com`, and the key is read from `AWS_BEARER_TOKEN_BEDROCK`, or from `~/.omp/agent/.env` where `set-key` stored it. To use another key or region:

```bash
export AWS_BEARER_TOKEN_BEDROCK=<your workshop key>
export AWS_REGION=eu-north-1
```

Your key works with these models; pick one with `--bedrock MODEL_ID` on `ftw.evaluate` or `--model MODEL_ID` on `ftw.generate`:

| Model ID | Notes | USD per 1M tokens (in / out) |
|---|---|---|
| `zai.glm-5` | default | 1.20 / 3.84 |
| `zai.glm-4.7` | faster, cheaper | 0.72 / 2.64 |
| `openai.gpt-oss-120b-1:0` | cheapest | 0.15 / 0.60 |
| `global.moonshotai.kimi-k3` | largest, most expensive | 3.00 / 15.00 |

Each key has a budget of about €25.

## Setup

Give the Podman VM 8 GB of memory. In the dev container:

```bash
uv sync
uv run python -m ftw.download
uv run pytest
```

`data/raw/glm5_raw.jsonl` holds 998 unchecked examples written by GLM-5. Never train on `data/eval.jsonl`.

## Tasks

1. **Baseline.** Score the untuned model (`uv run python -m ftw.evaluate`) and the teacher (`--bedrock zai.glm-5`).
2. **Training data.** Build `data/generated/train.jsonl`. Done when `FTW_TRAIN_DATA=data/generated/train.jsonl uv run pytest tests/test_datasets.py` passes. `ftw.generate` makes more; 1,000 examples cost about $0.30.
3. **Fine-tune.** `uv run python -m ftw.train --data data/generated/train.jsonl --output adapters/run1`, then `ftw.evaluate --adapter adapters/run1`. A run takes about 14 minutes; no run may take longer than 20. Done when an adapter scores at least **85% field accuracy, 55% exact match and 100% valid JSON**.
