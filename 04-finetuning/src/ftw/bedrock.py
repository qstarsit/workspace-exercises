"""Minimal Amazon Bedrock client for the workshop API key."""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import boto3
from botocore.config import Config

from ftw.prompt import Message

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

TOKEN_ENV: Final = "AWS_BEARER_TOKEN_BEDROCK"
OMP_ENV_FILE: Final = Path.home() / ".omp" / "agent" / ".env"
DEFAULT_REGION: Final = "eu-north-1"
DEFAULT_MODEL: Final = "zai.glm-5"

PRICES_PER_MILLION: Final[dict[str, tuple[float, float]]] = {
    "zai.glm-5": (1.20, 3.84),
}
"""USD per million (input, output) tokens, on-demand in eu-north-1, Nov 2026."""


@dataclass(frozen=True)
class Reply:
    """One Bedrock answer with its usage.

    Attributes:
        text: The model's text output.
        input_tokens: Billed input tokens.
        output_tokens: Billed output tokens.
        latency_seconds: Wall-clock time of the call.
    """

    text: str
    input_tokens: int
    output_tokens: int
    latency_seconds: float


def cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate the on-demand price of a number of tokens.

    Args:
        model_id: Bedrock model id.
        input_tokens: Input tokens.
        output_tokens: Output tokens.

    Returns:
        The cost in USD, or ``None`` if the model has no known price.
    """
    prices = PRICES_PER_MILLION.get(model_id)
    if prices is None:
        return None
    return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000


def _ensure_token() -> None:
    """Load the API key that ``set-key`` stored, unless the environment has one.

    Raises:
        RuntimeError: If no key can be found.
    """
    if os.environ.get(TOKEN_ENV):
        return
    if OMP_ENV_FILE.is_file():
        for line in OMP_ENV_FILE.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == TOKEN_ENV and value.strip():
                os.environ[TOKEN_ENV] = value.strip()
                return
    raise RuntimeError(f"No Bedrock key: set {TOKEN_ENV} or run set-key")


def make_client(max_connections: int = 16) -> "BedrockRuntimeClient":
    """Create a Bedrock runtime client that authenticates with the API key.

    Args:
        max_connections: Connection pool size, for calls from several threads.

    Returns:
        A boto3 ``bedrock-runtime`` client.

    Raises:
        RuntimeError: If no key can be found.
    """
    _ensure_token()
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", DEFAULT_REGION),
        config=Config(
            max_pool_connections=max_connections,
            retries={"max_attempts": 6, "mode": "adaptive"},
            read_timeout=300,
        ),
    )


def converse(
    client: "BedrockRuntimeClient",
    messages: list[Message],
    model_id: str = DEFAULT_MODEL,
    max_tokens: int = 256,
    temperature: float = 0.0,
) -> Reply:
    """Send one chat to Bedrock with the Converse API.

    Args:
        client: Client from :func:`make_client`.
        messages: Chat messages; ``system`` messages become the system prompt.
        model_id: Bedrock model id.
        max_tokens: Maximum output tokens.
        temperature: Sampling temperature.

    Returns:
        The answer and its usage.
    """
    system = [{"text": m["content"]} for m in messages if m["role"] == "system"]
    chat = [
        {"role": m["role"], "content": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]
    started = time.perf_counter()
    response = client.converse(
        modelId=model_id,
        system=system,  # type: ignore[arg-type]
        messages=chat,  # type: ignore[arg-type]
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    latency = time.perf_counter() - started
    blocks = response["output"]["message"]["content"]
    return Reply(
        text="".join(block.get("text", "") for block in blocks),
        input_tokens=response["usage"]["inputTokens"],
        output_tokens=response["usage"]["outputTokens"],
        latency_seconds=latency,
    )
