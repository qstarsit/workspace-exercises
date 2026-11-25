import httpx
import orjson
import pytest

from agent.model import BedrockClient, ModelError, Usage, create_bedrock_client

TOOLS = [{"toolSpec": {"name": "noop"}}]
MESSAGES = [{"role": "user", "content": [{"text": "hi"}]}]
REPLY = {
    "output": {"message": {"role": "assistant", "content": [{"text": "hello"}]}},
    "stopReason": "end_turn",
    "usage": {"inputTokens": 12, "outputTokens": 3, "totalTokens": 15},
}


def make_client(handler: httpx.MockTransport) -> BedrockClient:
    http = httpx.Client(
        base_url="https://bedrock-runtime.eu-north-1.amazonaws.com",
        headers={"Authorization": "Bearer test-token"},
        transport=handler,
    )
    return BedrockClient(http, "zai.glm-5")


def test_converse_request_and_response() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=REPLY)

    response = make_client(httpx.MockTransport(handler)).converse(
        MESSAGES, TOOLS, "be brief"
    )

    request = seen[0]
    assert request.url.path == "/model/zai.glm-5/converse"
    assert request.headers["Authorization"] == "Bearer test-token"
    assert orjson.loads(request.content) == {
        "messages": MESSAGES,
        "system": [{"text": "be brief"}],
        "toolConfig": {"tools": TOOLS},
    }
    assert response.message == REPLY["output"]["message"]  # type: ignore[index]
    assert response.stop_reason == "end_turn"
    assert response.usage == Usage(12, 3)


def test_tool_config_is_omitted_without_tools() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(200, json=REPLY)

    make_client(httpx.MockTransport(handler)).converse(MESSAGES, [], "s")

    assert "toolConfig" not in orjson.loads(bodies[0])


def test_error_status_raises_model_error() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(403, json={"message": "Bearer token expired"})
    )

    with pytest.raises(ModelError, match=r"403.*Bearer token expired"):
        make_client(transport).converse(MESSAGES, [], "s")


def test_network_failure_raises_model_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(ModelError, match="request failed"):
        make_client(httpx.MockTransport(handler)).converse(MESSAGES, [], "s")


def test_factory_targets_region_with_bearer_auth() -> None:
    client = create_bedrock_client("tok", "eu-north-1", "openai.gpt-oss-120b-1:0")

    assert client.model_id == "openai.gpt-oss-120b-1:0"
    assert (
        str(client._http.base_url) == "https://bedrock-runtime.eu-north-1.amazonaws.com"
    )
    assert client._http.headers["Authorization"] == "Bearer tok"
