from dataclasses import dataclass
from typing import Protocol

from agent.model import JsonObject, ModelClient
from agent.registry import ToolError, ToolRegistry

SYSTEM_PROMPT = """\
You are a coding agent working inside one repository, the workspace.
Use the tools to look at the code before you answer or change anything; do not
guess file contents. All paths are relative to the workspace root.
When the task is done, reply with a short summary of what you found or changed."""


class Reporter(Protocol):
    """Receives each step of a run so it can be shown to the user."""

    def assistant_text(self, text: str) -> None:
        """Show text the model wrote.

        Args:
            text: The text block.
        """
        ...

    def tool_call(self, name: str, arguments: JsonObject) -> None:
        """Show a tool call before it runs.

        Args:
            name: Tool name.
            arguments: Arguments from the model.
        """
        ...

    def tool_result(self, output: str, is_error: bool) -> None:
        """Show the result of a tool call.

        Args:
            output: What the tool returned (or the error message).
            is_error: Whether the call failed.
        """
        ...

    def finished(self, stop_reason: str) -> None:
        """Show that the run ended.

        Args:
            stop_reason: The model's final stop reason.
        """
        ...


@dataclass
class Agent:
    """The agent loop: ask the model, run the tools it asks for, repeat.

    Attributes:
        client: The model to talk to.
        registry: The tools the model may call.
        context: Passed to every tool as its first argument.
        reporter: Receives every step for display.
        system_prompt: Instructions sent with every model call.
    """

    client: ModelClient
    registry: ToolRegistry
    context: object
    reporter: Reporter
    system_prompt: str = SYSTEM_PROMPT

    def run(self, task: str) -> str:
        """Work on a task until the model stops asking for tools.

        Args:
            task: The user's request.

        Returns:
            The text of the model's final turn.
        """
        messages: list[JsonObject] = [{"role": "user", "content": [{"text": task}]}]
        while True:
            response = self.client.converse(
                messages, self.registry.specs, self.system_prompt
            )
            messages.append(response.message)
            blocks: list[JsonObject] = response.message["content"]
            for block in blocks:
                if "text" in block:
                    self.reporter.assistant_text(block["text"])
            if response.stop_reason != "tool_use":
                self.reporter.finished(response.stop_reason)
                return "\n".join(block["text"] for block in blocks if "text" in block)
            results = [
                self.call_tool(block["toolUse"])
                for block in blocks
                if "toolUse" in block
            ]
            messages.append({"role": "user", "content": results})

    def call_tool(self, tool_use: JsonObject) -> JsonObject:
        """Run one ``toolUse`` block and wrap the outcome as a ``toolResult``.

        Tool failures are reported back to the model instead of ending the run,
        so it can correct itself.

        Args:
            tool_use: The ``toolUse`` block (``toolUseId``, ``name``, ``input``).

        Returns:
            A ``toolResult`` content block for the next user message.
        """
        name, arguments = tool_use["name"], tool_use.get("input") or {}
        self.reporter.tool_call(name, arguments)
        result: JsonObject = {"toolUseId": tool_use["toolUseId"]}
        try:
            output = self.registry.run(name, arguments, self.context)
        except ToolError as error:
            output = f"Error: {error}"
            result["status"] = "error"
        self.reporter.tool_result(output, "status" in result)
        result["content"] = [{"text": output}]
        return {"toolResult": result}
