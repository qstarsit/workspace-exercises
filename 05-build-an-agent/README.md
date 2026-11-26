# Exercise 5: build your own coding agent

This folder holds a small working coding agent: a Converse loop on Bedrock with two read-only tools. Give it tools to search, test and edit code safely, then let it fix part of exercise 3.

## Bedrock

Everything is preset for the workshop: the endpoint is `https://bedrock-runtime.eu-north-1.amazonaws.com`, and the key is read from `AWS_BEARER_TOKEN_BEDROCK`, or from `~/.omp/agent/.env` where `set-key` stored it. To use another key or region:

```bash
export AWS_BEARER_TOKEN_BEDROCK=<your workshop key>
export AWS_REGION=eu-north-1
```

Your key works with these models; pick one with `--model MODEL_ID`:

| Model ID | Notes | USD per 1M tokens (in / out) |
|---|---|---|
| `zai.glm-5` | default | 1.20 / 3.84 |
| `zai.glm-4.7` | faster, cheaper | 0.72 / 2.64 |
| `openai.gpt-oss-120b-1:0` | cheapest | 0.15 / 0.60 |
| `global.moonshotai.kimi-k3` | largest, most expensive | 3.00 / 15.00 |

Each key has a budget of about €25.

## Setup

```bash
uv sync
uv run pytest      # only tests/test_acceptance_*.py fail
uv run agent "Summarise what this repository does" --workspace ../03-fastapi-feature
```

Do not edit `tests/acceptance.py` or the `test_acceptance_*.py` files.

## Important locations

| What | Where |
|---|---|
| System prompt | `SYSTEM_PROMPT` in `src/agent/loop.py` |
| The agent loop (model call, tool calls, results back) | `Agent.run` in `src/agent/loop.py` |
| Tools | `src/agent/tools.py`. A tool is a function decorated with `@registry.register`; its first parameter is the `ToolContext`, the rest become the tool's arguments. |
| What the model sees of a tool | The function name, the type hints, and the Google-style docstring (summary and `Args:`), turned into a JSON schema by `src/agent/registry.py` |
| Errors the model should see | Raise `ToolError` from a tool; the model gets the message with `status: error` |
| Workspace boundary | `Workspace.resolve` in `src/agent/workspace.py` |
| Bedrock call (Converse API) | `BedrockClient` in `src/agent/model.py` |
| What is printed per step | `ConsoleReporter` in `src/agent/console.py` |
| Command-line flags | `parse_args` in `src/agent/cli.py` |
| Tests without Bedrock | `ScriptedClient`, `text_turn` and `tool_turn` in `tests/support.py` replay prepared model turns |

## Tasks

Implement the following features:

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

## Bonus: reasoning mode

Add a `--reasoning` flag that lets the model think before it answers or calls a tool. Print its reasoning on the console, separate from its answer. Compare a capstone run with and without it: steps, tokens, cost and result.
