# Exercise 3: Add features to a FastAPI service

Fare Watch is a small FastAPI service on top of [Hermes](https://hermes.brinkhorst.dev/docs), a read-only API of observed Ryanair fares. Listing airports and the cheapest fares on a route already work. With your agent, add a deal check, a price trend and an upstream cache until the feature tests pass.

## Time budget

One workshop slot. Core: tasks 1 and 2. Stretch: task 3.

## Setup

```bash
uv sync
uv run pytest
```

Check: only tests in `tests/test_feature_*.py` fail. To try the API by hand: `uv run fastapi dev`, then open http://127.0.0.1:8000/docs.

## Reference for all tasks

- Hermes price history of one outbound date: `GET /api/v1/routes/{origin}/{destination}/history?outbound_date=YYYY-MM-DD&limit=1000`. It returns `points`, each with `observed_at`, `price` and `currency`. Recorded payloads are in `tests/fixtures/hermes/`.
- In new endpoints, `origin` and `destination` follow the same rules as on `/fares`.
- A Hermes error returns `502`; a Hermes timeout returns `504`.

## Tasks

Work with your agent; have it explain before it changes anything. Follow the existing structure, and do not edit the tests.

### 1. Deal check

`GET /routes/{origin}/{destination}/deal?outbound_date=YYYY-MM-DD`

- The current fare is the latest cheapest fare for that date, from Hermes `/cheapest?on=<outbound_date>`. If there is none, return `404` with `{"detail": "No fares observed yet for EIN-AGP on 2026-12-10"}`. An unknown route returns `404`, as on `/fares`.
- Compare the current price with every point in the date's history. The percentile rank is `(points below + points equal / 2) / total * 100`.
- Verdict: `cheap` if the rank is 25 or lower, `expensive` if it is 75 or higher, `normal` otherwise. With fewer than 5 points, the verdict is `insufficient_data` and `percentile` is `null`.
- Response: `origin`, `destination`, `outbound_date`, `price`, `currency`, `observed_at` (of the current fare), `verdict`, `percentile` (rounded to 1 decimal) and `sample_size` (number of history points).
- `outbound_date` is required; invalid input returns `422`.

Acceptance: `uv run pytest tests/test_feature_deal_check.py` passes.

### 2. Price trend

`GET /routes/{origin}/{destination}/trend?outbound_date=YYYY-MM-DD&days=14`

- `days` runs from 1 to 90 and defaults to 14. The window covers the `days` days up to and including the **most recent observation**, not the current time.
- Compare the first and last price in the window: `change = (last - first) / first * 100`. If `change` is +5 or more, the direction is `rising`; if it is -5 or less, `falling`; otherwise `flat`. Apply the thresholds to the unrounded value.
- With fewer than 2 points in the window, the direction is `insufficient_data` and `change_percent` is `null`.
- Response: `origin`, `destination`, `outbound_date`, `days`, `direction`, `change_percent` (rounded to 1 decimal) and `sample_size` (number of points in the window).
- Invalid input returns `422`.

Acceptance: `uv run pytest tests/test_feature_price_trend.py` passes.

### 3. Cache upstream calls

- Successful Hermes results are cached in memory, so repeated requests do not call Hermes again. Different parameters are cached separately: `/fares` and `/fares?on=...` are two entries.
- Entries expire after `HERMES_CACHE_TTL_SECONDS` (default 300). `0` disables the cache.
- Failures are never cached.

Acceptance: `uv run pytest tests/test_feature_cache.py` passes.

## Done when

- `uv run pytest` passes completely.
- `uv run ruff check . && uv run ruff format --check .` and `uv run mypy` are clean.
- No file in `tests/` was changed.
