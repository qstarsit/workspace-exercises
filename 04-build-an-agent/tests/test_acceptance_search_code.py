import re

from agent.workspace import Workspace
from tests.acceptance import AgentRunner, ToolOutcome
from tests.support import text_turn, tool_turn


def search(
    run_agent: AgentRunner, workspace: Workspace, **arguments: str | int
) -> ToolOutcome:
    run = run_agent(
        workspace.root, [tool_turn(("search_code", arguments)), text_turn("Done.")]
    )
    assert run.exit_code == 0
    [outcome] = run.tool_outcomes
    return outcome


def test_matches_are_path_line_text_relative_to_workspace(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    outcome = search(run_agent, workspace, pattern=r"def \w+")

    assert not outcome.is_error
    assert "src/pkg/core.py:1:def add(a, b):" in outcome.text.splitlines()


def test_path_glob_limits_the_files_searched(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    in_python = search(run_agent, workspace, pattern="demo", path_glob="*.py")
    in_markdown = search(run_agent, workspace, pattern="demo", path_glob="*.md")

    assert not in_python.is_error
    assert "README.md" not in in_python.text
    assert "README.md:2:A demo project." in in_markdown.text.splitlines()


def test_no_match_is_a_normal_result(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    outcome = search(run_agent, workspace, pattern="nothing-matches-this")

    assert not outcome.is_error


def test_max_results_caps_matches_and_reports_the_rest(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    (workspace.root / "many.txt").write_text("hit\n" * 10)

    outcome = search(run_agent, workspace, pattern="hit", max_results=3)

    lines = outcome.text.splitlines()
    assert lines[:3] == ["many.txt:1:hit", "many.txt:2:hit", "many.txt:3:hit"]
    assert sum(line.startswith("many.txt:") for line in lines) == 3
    assert re.search(r"\b7\b", outcome.text)


def test_default_cap_is_50(run_agent: AgentRunner, workspace: Workspace) -> None:
    (workspace.root / "many.txt").write_text("hit\n" * 60)

    outcome = search(run_agent, workspace, pattern="hit")

    lines = outcome.text.splitlines()
    assert sum(line.startswith("many.txt:") for line in lines) == 50
    assert re.search(r"\b10\b", outcome.text)


def test_long_lines_are_cut(run_agent: AgentRunner, workspace: Workspace) -> None:
    (workspace.root / "long.txt").write_text(f"needle{'x' * 5000}\n")

    outcome = search(run_agent, workspace, pattern="needle")

    assert outcome.text.startswith("long.txt:1:needle")
    assert len(outcome.text) < 1000


def test_invalid_regex_is_an_error_with_ripgreps_message(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    outcome = search(run_agent, workspace, pattern="(unclosed")

    assert outcome.is_error
    assert "regex parse error" in outcome.text


def test_pattern_starting_with_dash_is_a_pattern(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    (workspace.root / "flags.txt").write_text("use --files here\n")

    outcome = search(run_agent, workspace, pattern="--files")

    assert "flags.txt:1:use --files here" in outcome.text.splitlines()


def test_nothing_outside_the_workspace_is_searched(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    (workspace.root / "outside").symlink_to(workspace.root.parent)

    outcome = search(run_agent, workspace, pattern="do not read")

    assert not outcome.is_error
    assert "secret.txt" not in outcome.text
