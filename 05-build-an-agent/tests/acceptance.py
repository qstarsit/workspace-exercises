import io
import sys
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

from agent import cli
from agent.config import TOKEN_VARIABLE
from agent.model import JsonObject, ModelError, ModelResponse
from tests.support import ScriptedClient

BEDROCK_KEY = "acceptance-test-bedrock-key"


class FailingWhenEmptyClient(ScriptedClient):
    """A scripted model that fails like Bedrock once its prepared turns run out."""

    def converse(
        self, messages: list[JsonObject], tools: list[JsonObject], system: str
    ) -> ModelResponse:
        if not self.responses:
            raise ModelError("Bedrock returned 500: no scripted turns left")
        return super().converse(messages, tools, system)


@dataclass(frozen=True)
class ToolOutcome:
    """What the model was told about one tool call."""

    text: str
    is_error: bool


@dataclass(frozen=True)
class AgentRun:
    """The observable result of one ``agent`` command."""

    exit_code: int
    client: ScriptedClient
    output: str

    @property
    def tool_outcomes(self) -> list[ToolOutcome]:
        """Tool results sent to the model, in order, as of its last call."""
        if not self.client.calls:
            return []
        outcomes: list[ToolOutcome] = []
        for message in self.client.calls[-1].messages:
            for block in message["content"]:
                if "toolResult" in block:
                    result = block["toolResult"]
                    text = "".join(part.get("text", "") for part in result["content"])
                    outcomes.append(ToolOutcome(text, result.get("status") == "error"))
        return outcomes


@dataclass
class AgentRunner:
    """Runs the ``agent`` command against a scripted model instead of Bedrock."""

    monkeypatch: pytest.MonkeyPatch
    capsys: pytest.CaptureFixture[str]
    caplog: pytest.LogCaptureFixture

    def __call__(
        self,
        workspace: Path,
        turns: Iterable[ModelResponse],
        *options: str,
        stdin: str | None = None,
    ) -> AgentRun:
        """Run the CLI on ``workspace`` with ``options``.

        ``stdin`` is what the human types; ``None`` means reading it fails the
        test.
        """
        client = FailingWhenEmptyClient(deque(turns))
        self.monkeypatch.setenv(TOKEN_VARIABLE, BEDROCK_KEY)
        self.monkeypatch.setattr(cli, "create_bedrock_client", lambda *_: client)
        if stdin is not None:
            self.monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        exit_code = cli.main(["task", "--workspace", str(workspace), *options])
        captured = self.capsys.readouterr()
        return AgentRun(
            exit_code, client, f"{captured.out}{captured.err}{self.caplog.text}"
        )
