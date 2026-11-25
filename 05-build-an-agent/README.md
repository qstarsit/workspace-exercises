# Exercise 5: build your own coding agent

This folder holds a small working coding agent: a Converse loop on Bedrock with two read-only tools. Give it tools to search, test and edit code safely, then let it fix part of exercise 3.

## Setup

```bash
uv sync
uv run pytest      # only tests/test_acceptance_*.py fail
uv run agent "Summarise what this repository does" --workspace ../03-fastapi-feature
```

Do not edit `tests/acceptance.py` or the `test_acceptance_*.py` files.

## Tasks

### 1. `search_code(pattern, path_glob=None, max_results=50)`

Searches file contents in the workspace with ripgrep and returns `path:line:text` lines, capped at `max_results` with a count of what was left out. Nothing outside the workspace is searched.

Done when `uv run pytest tests/test_acceptance_search_code.py` passes.

### 2. `run_tests(path=None, keyword=None)`

Runs `uv run pytest` in the workspace and returns the exit code and output (at most about 20,000 characters). It stops after `TEST_TIMEOUT_SECONDS` in `agent/tools.py`, and the test process does not get `AWS_BEARER_TOKEN_BEDROCK`.

Done when `uv run pytest tests/test_acceptance_run_tests.py` passes.

### 3. `edit_file(path, old, new)`

Replaces `old` with `new` when it occurs exactly once, after showing a diff and getting `y` from the human. `--yes` approves without asking.

Done when `uv run pytest tests/test_acceptance_edit_file.py` passes.

### 4. Capstone: fix exercise 3 with your agent

```bash
rsync -a --exclude .venv ../03-fastapi-feature/ /tmp/fare-watch/
(cd /tmp/fare-watch && uv sync)
uv run agent "Make tests/test_feature_cache.py pass. Follow task 3 in README.md and \
the existing structure. Do not edit the tests." --workspace /tmp/fare-watch
```

Review every edit yourself, then give omp the same prompt on a fresh copy. Done when `tests/test_feature_cache.py` passes in the copy without breaking other tests, and you can say how your agent compared with omp.
