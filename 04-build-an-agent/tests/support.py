from collections import deque
from dataclasses import dataclass, field

from agent.model import JsonObject, ModelResponse, Usage


@dataclass
class ConverseCall:
    messages: list[JsonObject]
    tools: list[JsonObject]
    system: str


@dataclass
class ScriptedClient:
    """A fake model that replays prepared responses and records every call."""

    responses: deque[ModelResponse]
    calls: list[ConverseCall] = field(default_factory=list)

    def converse(
        self, messages: list[JsonObject], tools: list[JsonObject], system: str
    ) -> ModelResponse:
        self.calls.append(ConverseCall(list(messages), tools, system))
        return self.responses.popleft()


def text_turn(text: str, usage: Usage | None = None) -> ModelResponse:
    message = {"role": "assistant", "content": [{"text": text}]}
    return ModelResponse(message, "end_turn", usage or Usage(10, 5))


def tool_turn(
    *calls: tuple[str, JsonObject], text: str | None = None, usage: Usage | None = None
) -> ModelResponse:
    content: list[JsonObject] = [{"text": text}] if text else []
    content.extend(
        {"toolUse": {"toolUseId": f"call-{index}", "name": name, "input": arguments}}
        for index, (name, arguments) in enumerate(calls)
    )
    message = {"role": "assistant", "content": content}
    return ModelResponse(message, "tool_use", usage or Usage(10, 5))
