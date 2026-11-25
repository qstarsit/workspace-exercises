import os
import re
import sys
import time
from pathlib import Path

import orjson
import pytest

from agent import tools
from agent.model import JsonObject
from agent.workspace import Workspace
from tests.acceptance import AgentRunner
from tests.support import text_turn, tool_turn


def install_fake_uv(
    directory: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """Put a ``uv`` executable running the Python ``body`` first on ``PATH``."""
    bin_dir = directory / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(f"#!{sys.executable}\nimport os, sys, time\n{body}")
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def record_calls_to(record: Path) -> str:
    return f"""
import json
call = {{"argv": sys.argv[1:], "cwd": os.getcwd(), "environment": sorted(os.environ)}}
with open({str(record)!r}, "a") as file:
    file.write(json.dumps(call) + "\\n")
print("no tests ran in 0.01s")
sys.exit(5)
"""


def recorded_calls(record: Path) -> list[JsonObject]:
    if not record.exists():
        return []
    return [orjson.loads(line) for line in record.read_text().splitlines()]


@pytest.fixture
def record(
    workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    (workspace.root / "tests").mkdir()
    record = tmp_path / "uv-calls.txt"
    install_fake_uv(tmp_path, monkeypatch, record_calls_to(record))
    return record


def test_runs_uv_run_pytest_in_workspace_with_path_and_keyword(
    run_agent: AgentRunner, workspace: Workspace, record: Path
) -> None:
    arguments = {"path": "tests", "keyword": "add and not slow"}

    run = run_agent(
        workspace.root, [tool_turn(("run_tests", arguments)), text_turn("Done.")]
    )

    [outcome] = run.tool_outcomes
    [call] = recorded_calls(record)
    argv = call["argv"]
    assert argv[:2] == ["run", "pytest"]
    assert any(
        (workspace.root / argument).resolve() == workspace.root / "tests"
        for argument in argv[2:]
    )
    assert argv[argv.index("-k") + 1] == "add and not slow"
    assert Path(call["cwd"]).resolve() == workspace.root
    assert "no tests ran" in outcome.text
    assert re.search(r"\b5\b", outcome.text)


def test_test_process_does_not_get_the_bedrock_key(
    run_agent: AgentRunner, workspace: Workspace, record: Path
) -> None:
    run_agent(workspace.root, [tool_turn(("run_tests", {})), text_turn("Done.")])

    [call] = recorded_calls(record)
    assert "AWS_BEARER_TOKEN_BEDROCK" not in call["environment"]
    assert "PATH" in call["environment"]


def test_path_outside_workspace_is_refused(
    run_agent: AgentRunner, workspace: Workspace, record: Path
) -> None:
    turn = tool_turn(("run_tests", {"path": "../"}), ("run_tests", {"path": "tests"}))

    run = run_agent(workspace.root, [turn, text_turn("Done.")])

    outside, inside = run.tool_outcomes
    assert outside.is_error
    assert not inside.is_error
    assert len(recorded_calls(record)) == 1


def test_long_output_keeps_the_end(
    run_agent: AgentRunner,
    workspace: Workspace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = 'print("START OF OUTPUT")\nprint(("." * 99 + "\\n") * 1000)\n'
    body += 'print("=== 3 passed in 0.12s ===")\n'
    install_fake_uv(tmp_path, monkeypatch, body)

    run = run_agent(workspace.root, [tool_turn(("run_tests", {})), text_turn("Done.")])

    [outcome] = run.tool_outcomes
    assert "=== 3 passed in 0.12s ===" in outcome.text
    assert "START OF OUTPUT" not in outcome.text
    assert len(outcome.text) < 22_000


def test_timeout_stops_pytest_too_and_tells_the_model(
    run_agent: AgentRunner,
    workspace: Workspace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_marker = tmp_path / "pytest-started"
    alive_marker = tmp_path / "pytest-still-running"
    pytest_child = (
        f"import pathlib, time; pathlib.Path({str(started_marker)!r}).touch(); "
        f"time.sleep(3); pathlib.Path({str(alive_marker)!r}).touch()"
    )
    body = (
        "import subprocess\n"
        f"subprocess.Popen([sys.executable, '-c', {pytest_child!r}])\n"
        "time.sleep(60)\n"
    )
    install_fake_uv(tmp_path, monkeypatch, body)
    monkeypatch.setattr(tools, "TEST_TIMEOUT_SECONDS", 1.0)

    started = time.monotonic()
    run = run_agent(workspace.root, [tool_turn(("run_tests", {})), text_turn("Done.")])
    elapsed = time.monotonic() - started

    [outcome] = run.tool_outcomes
    assert re.search(r"timed?\W?out", outcome.text, re.IGNORECASE)
    assert started_marker.exists(), "the fake pytest did not start in time"
    assert elapsed < 2.5
    time.sleep(3.5 - elapsed)
    assert not alive_marker.exists()
