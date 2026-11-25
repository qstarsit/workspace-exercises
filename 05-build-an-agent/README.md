# Exercise 5: build your own coding agent

This folder holds a small working coding agent: a Converse loop on Bedrock with two read-only tools, `list_files` and `read_file`. Extend it until it can search, test and edit code safely, then let it fix part of exercise 3 and compare it with omp.

## Time budget

About 90 minutes. Core: tasks 1 to 4. Capstone: task 5; one GLM-5 run costs about $0.50.

## Setup

```bash
uv sync
uv run pytest
uv run agent "Summarise what this repository does" --workspace ../03-fastapi-feature
```

Check: only tests in `tests/test_acceptance_*.py` fail, and the agent answers. It uses the key that `set-key` stored for omp; the default model is `zai.glm-5`, and `--model` picks another.

## Tasks

Work with your agent; have it explain before it changes anything. Do not edit the `test_acceptance_*.py` files or `tests/acceptance.py`. Tests never call Bedrock.

### 1. `search_code(pattern, path_glob=None, max_results=50)`

- Searches file contents with ripgrep (`rg`) in the workspace. `pattern` is a regular expression; `path_glob` limits the files searched.
- Returns one `path:line:text` line per match, paths relative to the workspace, at most `max_results` matches, plus how many were left out. Very long lines are cut.
- No matches is a normal result. An invalid regex is an error with ripgrep's message.
- A pattern that starts with `-` is searched for. Nothing outside the workspace is searched.

Acceptance: `uv run pytest tests/test_acceptance_search_code.py` passes.

### 2. `run_tests(path=None, keyword=None)`

- Runs `uv run pytest` in the workspace root. `path` is confined to the workspace; `keyword` is passed as `-k`.
- Returns the exit code and the output. Long output is shortened to at most about 20,000 characters and keeps the end.
- Stops after `TEST_TIMEOUT_SECONDS`, a constant in `agent/tools.py`. On timeout, every process it started is stopped and the model is told.
- The test process does not get `AWS_BEARER_TOKEN_BEDROCK`.

Acceptance: `uv run pytest tests/test_acceptance_run_tests.py` passes.

### 3. `edit_file(path, old, new)`

- Replaces `old` with `new` when `old` occurs exactly once. Otherwise it is an error that says how many times `old` was found, and the file is unchanged.
- Before writing, prints a unified diff and asks the human `y/n`. Only `y` or `yes` approves; anything else leaves the file unchanged and tells the model the edit was rejected.
- `--yes` approves every edit without asking, and still prints the diff.
- The path is confined to the workspace. The file keeps its line endings.

Acceptance: `uv run pytest tests/test_acceptance_edit_file.py` passes.

### 4. Guardrails

- `--max-steps N` (default 30) stops the run after N model calls, with a message and a non-zero exit code.
- Every run prints its total input and output tokens and its cost in USD, also when it stopped early or the model call failed.
- Prices are the on-demand prices for `eu-north-1`. Write the source and the date you checked them next to the numbers. For a model without a price, the cost is reported as unknown.
- There is no shell tool.

Acceptance: `uv run pytest tests/test_acceptance_guardrails.py` passes.

### 5. Capstone: fix exercise 3 with your agent

Work on a copy, so your own exercise 3 stays as it is:

```bash
rsync -a --exclude .venv ../03-fastapi-feature/ /tmp/fare-watch/
(cd /tmp/fare-watch && uv sync)
uv run agent "Make tests/test_feature_cache.py pass. Follow task 3 in README.md and \
the existing structure. Do not edit the tests." --workspace /tmp/fare-watch
```

Review and approve every edit yourself: no `--yes`. Then give omp the same prompt on a fresh copy.

Acceptance: `tests/test_feature_cache.py` passes in the copy, the tests that passed before still pass, and you have noted for both agents the steps, tokens, cost and what `uv run ruff check .` and `uv run mypy` report afterwards.

## Done when

- `uv run pytest`, `uv run ruff check . && uv run ruff format --check .` and `uv run mypy` are clean.
- The capstone comparison between your agent and omp is written down.

## Questions

- Why no shell tool? `run_tests` can run any test the agent writes: what makes that acceptable here, and would it be on your laptop?
- What did your agent get wrong in the capstone, and which of those mistakes came from how you designed its tools?
- Where did the tokens go, and why does the input grow with every step?
- How did your agent compare with omp on steps, cost, result and how often you had to step in?
- What would you add before you trusted this agent on real code?
