from collections import deque
from pathlib import Path

import pytest

from agent import cli
from agent.config import TOKEN_VARIABLE, MissingTokenError
from agent.model import BedrockClient
from tests.support import ScriptedClient, text_turn, tool_turn


def test_parse_args_defaults() -> None:
    args = cli.parse_args(["explain"])

    assert args.task == "explain"
    assert args.workspace == Path()
    assert args.model == "zai.glm-5"
    assert args.region == "eu-north-1"


def test_main_runs_agent_and_prints_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.txt").write_text("alpha\n")
    client = ScriptedClient(
        deque(
            [tool_turn(("read_file", {"path": "a.txt"})), text_turn("It says alpha.")]
        )
    )
    monkeypatch.setenv(TOKEN_VARIABLE, "tok")

    def fake_factory(token: str, region: str, model_id: str) -> BedrockClient:
        assert (token, region, model_id) == ("tok", "eu-north-1", "zai.glm-5")
        return client  # type: ignore[return-value]

    monkeypatch.setattr(cli, "create_bedrock_client", fake_factory)

    exit_code = cli.main(["what is in a.txt?", "--workspace", str(tmp_path)])

    printed = capsys.readouterr().out
    assert exit_code == 0
    assert '[1] read_file(path="a.txt")' in printed
    assert "It says alpha." in printed


def test_main_fails_cleanly_without_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def no_token() -> str:
        raise MissingTokenError("Set AWS_BEARER_TOKEN_BEDROCK")

    monkeypatch.setattr(cli, "load_bearer_token", no_token)

    assert cli.main(["task", "--workspace", str(tmp_path)]) == 1
    assert "Set AWS_BEARER_TOKEN_BEDROCK" in caplog.text


def test_main_fails_cleanly_on_missing_workspace(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    assert cli.main(["task", "--workspace", str(tmp_path / "nope")]) == 1
    assert "nope" in caplog.text
