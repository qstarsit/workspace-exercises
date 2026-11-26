from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import orjson

type JsonObject = dict[str, Any]


class ModelError(RuntimeError):
    """Raised when the model API rejects a request or cannot be reached."""


@dataclass(frozen=True)
class Usage:
    """Tokens consumed by one model call."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ModelResponse:
    """One assistant turn returned by the model.

    Attributes:
        message: The assistant message in Converse format (``role`` and
            ``content`` blocks). Append it to the conversation unchanged.
        stop_reason: Why the model stopped, e.g. ``end_turn`` or ``tool_use``.
        usage: Tokens consumed by this call.
    """

    message: JsonObject
    stop_reason: str
    usage: Usage


class ModelClient(Protocol):
    """Anything that can take a conversation and return the next assistant turn."""

    def converse(
        self, messages: list[JsonObject], tools: list[JsonObject], system: str
    ) -> ModelResponse:
        """Send the conversation and return the model's next turn.

        Args:
            messages: The conversation so far, oldest first.
            tools: Tool specs in Converse ``toolSpec`` format.
            system: The system prompt.

        Returns:
            The assistant's next turn.
        """
        ...


class BedrockClient:
    """Calls the Bedrock Converse API with a bearer token over plain HTTP."""

    def __init__(self, http: httpx.Client, model_id: str) -> None:
        self._http = http
        self.model_id = model_id

    def converse(
        self, messages: list[JsonObject], tools: list[JsonObject], system: str
    ) -> ModelResponse:
        """Send the conversation to Bedrock and return the next assistant turn.

        Args:
            messages: The conversation so far, oldest first.
            tools: Tool specs in Converse ``toolSpec`` format.
            system: The system prompt.

        Returns:
            The assistant's next turn.

        Raises:
            ModelError: If the request fails or Bedrock returns an error status.
        """
        body: JsonObject = {"messages": messages, "system": [{"text": system}]}
        if tools:
            body["toolConfig"] = {"tools": tools}
        try:
            response = self._http.post(
                f"/model/{self.model_id}/converse",
                content=orjson.dumps(body),
                headers={"Content-Type": "application/json"},
            )
        except httpx.HTTPError as error:
            raise ModelError(f"Bedrock request failed: {error}") from error
        if response.is_error:
            raise ModelError(
                f"Bedrock returned {response.status_code}: {response.text}"
            )
        payload = orjson.loads(response.content)
        usage = payload.get("usage", {})
        return ModelResponse(
            message=payload["output"]["message"],
            stop_reason=payload["stopReason"],
            usage=Usage(usage.get("inputTokens", 0), usage.get("outputTokens", 0)),
        )


def create_bedrock_client(token: str, region: str, model_id: str) -> BedrockClient:
    """Build a Bedrock client that authenticates with a bearer token.

    Args:
        token: The Bedrock API key (bearer token).
        region: AWS region, e.g. ``eu-north-1``.
        model_id: Bedrock model ID, e.g. ``zai.glm-5``.

    Returns:
        A ready-to-use client. Closing it is left to process exit.
    """
    http = httpx.Client(
        base_url=f"https://bedrock-runtime.{region}.amazonaws.com",
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(300.0, connect=10.0),
    )
    return BedrockClient(http, model_id)
