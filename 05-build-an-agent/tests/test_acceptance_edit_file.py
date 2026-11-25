import re

import pytest

from agent.model import ModelResponse
from agent.workspace import Workspace
from tests.acceptance import AgentRunner
from tests.support import text_turn, tool_turn

ALPHA_TO_BETA = ("edit_file", {"path": "a.txt", "old": "alpha", "new": "beta"})


def edit_turns(*calls: tuple[str, dict[str, str]]) -> list[ModelResponse]:
    return [tool_turn(*calls), text_turn("Done.")]


@pytest.fixture
def a_txt(workspace: Workspace) -> Workspace:
    (workspace.root / "a.txt").write_text("alpha\n")
    return workspace


@pytest.mark.parametrize("answer", ["y\n", "yes\n"])
def test_approved_edit_shows_diff_and_writes(
    run_agent: AgentRunner, a_txt: Workspace, answer: str
) -> None:
    run = run_agent(a_txt.root, edit_turns(ALPHA_TO_BETA), stdin=answer)

    [outcome] = run.tool_outcomes
    assert not outcome.is_error
    assert (a_txt.root / "a.txt").read_text() == "beta\n"
    assert "-alpha" in run.output
    assert "+beta" in run.output


@pytest.mark.parametrize("answer", ["n\n", "\n", "maybe\n", ""])
def test_anything_but_yes_rejects_the_edit(
    run_agent: AgentRunner, a_txt: Workspace, answer: str
) -> None:
    run = run_agent(a_txt.root, edit_turns(ALPHA_TO_BETA), stdin=answer)

    [outcome] = run.tool_outcomes
    assert run.exit_code == 0
    assert (a_txt.root / "a.txt").read_text() == "alpha\n"
    assert re.search(r"reject", outcome.text, re.IGNORECASE)


def test_yes_flag_approves_without_asking_and_still_shows_diff(
    run_agent: AgentRunner, a_txt: Workspace
) -> None:
    run = run_agent(a_txt.root, edit_turns(ALPHA_TO_BETA), "--yes")

    assert run.exit_code == 0
    assert (a_txt.root / "a.txt").read_text() == "beta\n"
    assert "-alpha" in run.output
    assert "+beta" in run.output


@pytest.mark.parametrize(("content", "count"), [("gamma\n", 0), ("x\nx\n", 2)])
def test_old_must_occur_exactly_once(
    run_agent: AgentRunner, workspace: Workspace, content: str, count: int
) -> None:
    file = workspace.root / "b.txt"
    file.write_text(content)
    edit = ("edit_file", {"path": "b.txt", "old": "x", "new": "y"})

    run = run_agent(workspace.root, edit_turns(edit), "--yes")

    [outcome] = run.tool_outcomes
    assert outcome.is_error
    assert re.search(rf"\b{count}\b", outcome.text)
    assert file.read_text() == content


def test_paths_outside_the_workspace_are_refused(
    run_agent: AgentRunner, a_txt: Workspace
) -> None:
    secret = a_txt.root.parent / "secret.txt"
    outside = ("edit_file", {"path": "../secret.txt", "old": "do not", "new": "do"})

    run = run_agent(a_txt.root, edit_turns(ALPHA_TO_BETA, outside), "--yes")

    inside_outcome, outside_outcome = run.tool_outcomes
    assert not inside_outcome.is_error
    assert outside_outcome.is_error
    assert secret.read_text() == "do not read\n"


def test_line_endings_are_kept(run_agent: AgentRunner, workspace: Workspace) -> None:
    file = workspace.root / "crlf.txt"
    file.write_bytes(b"one\r\ntwo\r\n")
    edit = ("edit_file", {"path": "crlf.txt", "old": "two", "new": "three"})

    run_agent(workspace.root, edit_turns(edit), "--yes")

    assert file.read_bytes() == b"one\r\nthree\r\n"
