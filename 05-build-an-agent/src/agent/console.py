import sys
from typing import TextIO

import orjson

from agent.model import JsonObject

PREVIEW_CHARS = 160


class ConsoleReporter:
    """Prints each step of a run in a compact, readable form."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout
        self._calls = 0

    def _write(self, text: str) -> None:
        self._stream.write(f"{text}\n")
        self._stream.flush()

    def assistant_text(self, text: str) -> None:
        """Print text the model wrote.

        Args:
            text: The text block.
        """
        self._write(f"\n{text.strip()}\n")

    def tool_call(self, name: str, arguments: JsonObject) -> None:
        """Print a numbered tool call with its arguments.

        Args:
            name: Tool name.
            arguments: Arguments from the model.
        """
        self._calls += 1
        rendered = ", ".join(
            f"{key}={orjson.dumps(value).decode()}" for key, value in arguments.items()
        )
        self._write(f"[{self._calls}] {name}({preview(rendered)})")

    def tool_result(self, output: str, is_error: bool) -> None:
        """Print the first line of a tool result and its size.

        Args:
            output: What the tool returned.
            is_error: Whether the call failed.
        """
        first_line = output.strip().partition("\n")[0]
        lines = output.count("\n") + 1
        label = "error" if is_error else f"{lines} lines"
        self._write(f"    -> {label}: {preview(first_line)}")

    def finished(self, stop_reason: str) -> None:
        """Print how the run ended.

        Args:
            stop_reason: The model's final stop reason.
        """
        self._write(f"[done: {stop_reason}, {self._calls} tool calls]")


def preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    """Shorten text to one display line.

    Args:
        text: Text to shorten.
        limit: Maximum number of characters.

    Returns:
        The text, cut with an ellipsis if it is longer than ``limit``.
    """
    return text if len(text) <= limit else f"{text[: limit - 3]}..."
