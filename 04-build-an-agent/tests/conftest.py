from pathlib import Path

import pytest

from agent.tools import ToolContext
from agent.workspace import Workspace
from tests.acceptance import AgentRunner


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    root = tmp_path / "repo"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "README.md").write_text("# Demo\nA demo project.\n")
    (root / "src" / "pkg" / "core.py").write_text("def add(a, b):\n    return a + b\n")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "secret.txt").write_text("do not read\n")
    return Workspace(root)


@pytest.fixture
def context(workspace: Workspace) -> ToolContext:
    return ToolContext(workspace)


@pytest.fixture
def run_agent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> AgentRunner:
    return AgentRunner(monkeypatch, capsys, caplog)
