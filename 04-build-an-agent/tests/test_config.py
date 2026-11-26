from pathlib import Path

import pytest

from agent.config import TOKEN_VARIABLE, MissingTokenError, load_bearer_token


@pytest.fixture(autouse=True)
def no_token_in_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)


def test_environment_variable_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"{TOKEN_VARIABLE}=from-file\n")
    monkeypatch.setenv(TOKEN_VARIABLE, "from-env")

    assert load_bearer_token(env_file) == "from-env"


@pytest.mark.parametrize(
    "line",
    [
        f"{TOKEN_VARIABLE}=abc123",
        f"export {TOKEN_VARIABLE}='abc123'",
        f' {TOKEN_VARIABLE} = "abc123" ',
    ],
)
def test_token_is_read_from_env_file(tmp_path: Path, line: str) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"# omp settings\nOTHER=1\n{line}\n")

    assert load_bearer_token(env_file) == "abc123"


@pytest.mark.parametrize("content", [None, "OTHER=1\n", f"{TOKEN_VARIABLE}=\n"])
def test_missing_token_raises(tmp_path: Path, content: str | None) -> None:
    env_file = tmp_path / ".env"
    if content is not None:
        env_file.write_text(content)

    with pytest.raises(MissingTokenError, match="set-key"):
        load_bearer_token(env_file)
