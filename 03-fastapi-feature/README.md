# Exercise 3: Add features to a FastAPI service

Fare Watch is a small FastAPI service on top of [Hermes](https://hermes.brinkhorst.dev/docs), a read-only API of observed Ryanair fares. Add a deal check, a price trend and an upstream cache. Follow the existing structure and do not edit the tests.

## Setup

```bash
uv sync
uv run pytest      # only tests/test_feature_*.py fail
```

## Tasks

### 1. Deal check

`GET /routes/{origin}/{destination}/deal?outbound_date=YYYY-MM-DD`

- The current fare is the latest cheapest fare for that date (Hermes `/cheapest?on=<outbound_date>`). None: `404` with `{"detail": "No fares observed yet for EIN-AGP on 2026-12-10"}`.
- Percentile rank of the current price against the date's history: `(points below + points equal / 2) / total * 100`.
- Verdict: `cheap` at 25 or lower, `expensive` at 75 or higher, otherwise `normal`. Fewer than 5 points: `insufficient_data`, `percentile` is `null`.
- Response: `origin`, `destination`, `outbound_date`, `price`, `currency`, `observed_at`, `verdict`, `percentile` (1 decimal), `sample_size`.

Done when `uv run pytest tests/test_feature_deal_check.py` passes.

### 2. Price trend

`GET /routes/{origin}/{destination}/trend?outbound_date=YYYY-MM-DD&days=14`

- `days`: 1 to 90, default 14. The window ends at the most recent observation, not now.
- `change = (last - first) / first * 100` over the window: `rising` at +5 or more, `falling` at -5 or less, otherwise `flat` (thresholds on the unrounded value). Fewer than 2 points: `insufficient_data`, `change_percent` is `null`.
- Response: `origin`, `destination`, `outbound_date`, `days`, `direction`, `change_percent` (1 decimal), `sample_size`.

Done when `uv run pytest tests/test_feature_price_trend.py` passes.

### 3. Cache upstream calls

Cache successful Hermes results in memory, per set of parameters, for `HERMES_CACHE_TTL_SECONDS` (default 300; `0` disables it). Never cache failures.

Done when `uv run pytest tests/test_feature_cache.py` passes, and `uv run ruff check .` and `uv run mypy` are clean.
