# Exercise 3: add a feature to a FastAPI service

Fare Watch is a small API on top of [Hermes](https://hermes.brinkhorst.dev/docs), an
unofficial, read-only API for Ryanair flight prices. Hermes scrapes every route and
stores each price it sees, append-only. A Hermes price is an **observation** taken at
`observed_at`, not a live offer, and the code names reflect that.

Listing airports and fetching the cheapest observed fares on a route already work. Your
job is to add the missing features with your AI coding agent, following the structure
that is already in place.

## Structure

```
src/fare_watch/
  main.py                 app factory (create_app) and lifespan (owns the httpx client)
  config.py               settings (pydantic-settings, HERMES_* env vars)
  dependencies.py         FastAPI dependencies and Annotated aliases
  domain.py               domain models (dataclasses) and domain exceptions
  schemas.py              request/response models (pydantic)
  exception_handlers.py   maps domain exceptions to HTTP status codes
  routers/                HTTP layer: health, airports, fares
  services/               use cases and business rules
  clients/
    base.py               HermesClient protocol
    hermes.py             httpx implementation; parses Hermes payloads into domain objects
tests/
  conftest.py             fixtures: respx-mocked Hermes, test clients, payload helpers
  support.py              FakeHermesClient (injected via dependency_overrides)
  fixtures/hermes/        real Hermes responses recorded for EIN-AGP
  test_*.py               tests for existing behaviour (pass)
  test_feature_*.py       tests for the features you build (fail until you are done)
```

A request flows `router -> service -> client`. Routers translate HTTP to service calls,
services hold the rules, and the client is the only code that knows Hermes URLs and
payloads. Upstream failures become domain exceptions, which `exception_handlers.py`
maps to status codes. Tests never touch the network: they mock Hermes with
[respx](https://lundberg.github.io/respx/), or replace the client through
`app.dependency_overrides`.

## Run it

```bash
uv sync
uv run fastapi dev        # http://127.0.0.1:8000/docs
```

Try `GET /airports?country=nl` or `GET /routes/EIN/AGP/fares`. Guest access to Hermes
needs no key. To use a key, set `HERMES_API_KEY` in `.env` (see `.env.example`).

## Test and check

```bash
uv run pytest                                   # everything
uv run pytest tests/test_feature_deal_check.py  # one feature
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

Done means: all tests pass, and Ruff and mypy are clean. Do not edit the tests.

## Your tasks

Start by asking the agent to explain the architecture and how a request flows through
the layers. Then do the tasks one at a time, running the matching test file after each.
Read `tests/fixtures/hermes/` and the [Hermes docs](https://hermes.brinkhorst.dev/docs)
for payload shapes.

Tasks 1 and 2 need the price history of one outbound date:
`GET /api/v1/routes/{origin}/{destination}/history?outbound_date=YYYY-MM-DD&limit=1000`.
It returns `points`, each with `observed_at`, `price` and `currency`. Add this to the
client layer once and reuse it.

For all new endpoints, `origin` and `destination` follow the same rules as on `/fares`.
Use the existing domain exceptions to report Hermes failures: 502 for errors, 504 for
timeouts.

### 1. Deal check (`tests/test_feature_deal_check.py`)

`GET /routes/{origin}/{destination}/deal?outbound_date=YYYY-MM-DD`

- The current fare is the latest cheapest fare for that date, from Hermes
  `/cheapest?on=<outbound_date>`. If there is none, return `404` with
  `{"detail": "No fares observed yet for EIN-AGP on 2026-12-10"}`. An unknown route
  returns `404`, as on `/fares`.
- Compare the current price with every point in the date's history. The percentile rank
  is `(points below + points equal / 2) / total * 100`.
- Verdict: `cheap` if the rank is 25 or lower, `expensive` if it is 75 or higher,
  `normal` otherwise. With fewer than 5 points, the verdict is `insufficient_data` and
  `percentile` is `null`.
- Response: `origin`, `destination`, `outbound_date`, `price`, `currency`,
  `observed_at` (of the current fare), `verdict`, `percentile` (rounded to 1 decimal)
  and `sample_size` (number of history points).
- `outbound_date` is required; invalid input returns `422`.

### 2. Price trend (`tests/test_feature_price_trend.py`)

`GET /routes/{origin}/{destination}/trend?outbound_date=YYYY-MM-DD&days=14`

- `days` runs from 1 to 90 and defaults to 14. The window covers the `days` days up to
  and including the **most recent observation**, not the current time.
- Compare the first and last price in the window:
  `change = (last - first) / first * 100`. If `change` is +5 or more, the direction is
  `rising`; if it is -5 or less, `falling`; otherwise `flat`. Apply the thresholds to
  the unrounded value.
- With fewer than 2 points in the window, the direction is `insufficient_data` and
  `change_percent` is `null`.
- Response: `origin`, `destination`, `outbound_date`, `days`, `direction`,
  `change_percent` (rounded to 1 decimal) and `sample_size` (number of points in the
  window).
- Invalid input returns `422`.

### 3. Cache upstream calls (`tests/test_feature_cache.py`)

- Cache successful Hermes results in memory, so repeated requests do not call Hermes
  again. The cache key includes the parameters, so `/fares` and `/fares?on=...` are
  cached separately.
- Entries expire after `HERMES_CACHE_TTL_SECONDS` (default 300). `0` disables the cache.
- Failures are never cached.
- The cache belongs to the app instance: create it in the lifespan and inject it.
  Do not use a module-level global, or tests will leak state into each other.
