import re

from agent.model import ModelResponse, Usage
from agent.workspace import Workspace
from tests.acceptance import AgentRun, AgentRunner
from tests.support import text_turn, tool_turn


def looping_turns(count: int, usage: Usage | None = None) -> list[ModelResponse]:
    return [tool_turn(("list_files", {}), usage=usage) for _ in range(count)]


def numbers_in(run: AgentRun) -> set[int]:
    return {int(number) for number in re.findall(r"\d+", run.output.replace(",", ""))}


def printed_costs(run: AgentRun) -> list[float]:
    return [float(cost) for cost in re.findall(r"\$\s*(\d+(?:\.\d+)?)", run.output)]


def test_max_steps_stops_the_run(run_agent: AgentRunner, workspace: Workspace) -> None:
    run = run_agent(workspace.root, looping_turns(5), "--max-steps", "2")

    assert run.exit_code != 0
    assert len(run.client.calls) == 2
    assert "step" in run.output.lower()


def test_max_steps_defaults_to_30(run_agent: AgentRunner, workspace: Workspace) -> None:
    run = run_agent(workspace.root, looping_turns(40))

    assert run.exit_code != 0
    assert len(run.client.calls) == 30


def test_tokens_and_cost_are_printed_after_a_run(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    turns = [
        tool_turn(("list_files", {}), usage=Usage(600_000, 20_000)),
        text_turn("Done.", usage=Usage(400_000, 30_000)),
    ]

    run = run_agent(workspace.root, turns)

    assert run.exit_code == 0
    assert {1_000_000, 50_000} <= numbers_in(run)
    assert any(cost > 0 for cost in printed_costs(run))


def test_tokens_are_printed_when_the_step_limit_stops_the_run(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    run = run_agent(
        workspace.root, looping_turns(5, Usage(1_234, 56)), "--max-steps", "2"
    )

    assert run.exit_code != 0
    assert {2_468, 112} <= numbers_in(run)


def test_tokens_are_printed_when_the_model_fails(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    run = run_agent(workspace.root, looping_turns(1, Usage(4_321, 87)))

    assert run.exit_code != 0
    assert {4_321, 87} <= numbers_in(run)


def test_model_without_price_reports_cost_unknown(
    run_agent: AgentRunner, workspace: Workspace
) -> None:
    run = run_agent(
        workspace.root, [text_turn("Hi.")], "--model", "acme.unpriced-model-v1"
    )

    assert run.exit_code == 0
    assert "unknown" in run.output.lower()
    assert printed_costs(run) == []
