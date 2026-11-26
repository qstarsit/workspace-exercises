import os
from pathlib import Path

import pytest

from ftw import bedrock


def test_cost_of_known_and_unknown_models() -> None:
    assert bedrock.cost_usd("zai.glm-5", 1_000_000, 1_000_000) == pytest.approx(5.04)
    assert bedrock.cost_usd("unknown.model", 10, 10) is None


def test_token_falls_back_to_set_key_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=1\nAWS_BEARER_TOKEN_BEDROCK=abc123\n")
    monkeypatch.delenv(bedrock.TOKEN_ENV, raising=False)
    monkeypatch.setattr(bedrock, "OMP_ENV_FILE", env_file)

    bedrock._ensure_token()

    assert os.environ[bedrock.TOKEN_ENV] == "abc123"


def test_missing_token_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(bedrock.TOKEN_ENV, raising=False)
    monkeypatch.setattr(bedrock, "OMP_ENV_FILE", tmp_path / "missing")

    with pytest.raises(RuntimeError, match="set-key"):
        bedrock._ensure_token()
