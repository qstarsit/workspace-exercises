import io
from collections import deque

from agent.console import ConsoleReporter
from agent.loop import SYSTEM_PROMPT, Agent
from agent.tools import ToolContext, registry
from tests.support import ScriptedClient, text_turn, tool_turn


def make_agent(
    client: ScriptedClient, context: ToolContext
) -> tuple[Agent, io.StringIO]:
    output = io.StringIO()
    return Agent(client, registry, context, ConsoleReporter(output)), output


def test_plain_answer_ends_after_one_call(context: ToolContext) -> None:
    client = ScriptedClient(deque([text_turn("Nothing to do.")]))
    agent, output = make_agent(client, context)

    answer = agent.run("Say hi")

    assert answer == "Nothing to do."
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call.messages == [{"role": "user", "content": [{"text": "Say hi"}]}]
    assert call.system == SYSTEM_PROMPT
    assert [t["toolSpec"]["name"] for t in call.tools] == ["list_files", "read_file"]
    assert "[done: end_turn, 0 tool calls]" in output.getvalue()


def test_tool_result_is_sent_back_with_matching_id(context: ToolContext) -> None:
    client = ScriptedClient(
        deque(
            [
                tool_turn(("read_file", {"path": "README.md"}), text="Let me look."),
                text_turn("It is a demo."),
            ]
        )
    )
    agent, output = make_agent(client, context)

    answer = agent.run("What is this?")

    assert answer == "It is a demo."
    messages = client.calls[1].messages
    assert messages[1]["role"] == "assistant"
    assert messages[2] == {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": "call-0",
                    "content": [{"text": "# Demo\nA demo project."}],
                }
            }
        ],
    }
    printed = output.getvalue()
    assert '[1] read_file(path="README.md")' in printed
    assert "-> 2 lines: # Demo" in printed


def test_parallel_tool_calls_are_answered_in_one_message(
    context: ToolContext,
) -> None:
    client = ScriptedClient(
        deque(
            [
                tool_turn(
                    ("list_files", {}), ("read_file", {"path": "src/pkg/core.py"})
                ),
                text_turn("Done."),
            ]
        )
    )
    agent, _ = make_agent(client, context)

    agent.run("Explore")

    results = client.calls[1].messages[2]["content"]
    assert [r["toolResult"]["toolUseId"] for r in results] == ["call-0", "call-1"]


def test_tool_errors_are_reported_to_the_model(context: ToolContext) -> None:
    client = ScriptedClient(
        deque(
            [
                tool_turn(("read_file", {"path": "../secret.txt"})),
                tool_turn(("delete_everything", {})),
                text_turn("I cannot."),
            ]
        )
    )
    agent, output = make_agent(client, context)

    agent.run("Read the secret")

    first = client.calls[1].messages[2]["content"][0]["toolResult"]
    second = client.calls[2].messages[4]["content"][0]["toolResult"]
    assert first["status"] == "error"
    assert (
        first["content"][0]["text"] == "Error: ../secret.txt is outside the workspace"
    )
    assert second["status"] == "error"
    assert second["content"][0]["text"].startswith("Error: Unknown tool")
    assert "-> error: Error: ../secret.txt is outside" in output.getvalue()


def test_other_stop_reasons_end_the_run(context: ToolContext) -> None:
    truncated = text_turn("Partial")
    client = ScriptedClient(
        deque([type(truncated)(truncated.message, "max_tokens", truncated.usage)])
    )
    agent, output = make_agent(client, context)

    assert agent.run("Write a novel") == "Partial"
    assert "[done: max_tokens" in output.getvalue()
