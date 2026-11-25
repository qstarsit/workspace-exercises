import os
from pathlib import Path

DEFAULT_MODEL_ID = "zai.glm-5"
DEFAULT_REGION = "eu-north-1"
TOKEN_VARIABLE = "AWS_BEARER_TOKEN_BEDROCK"
OMP_ENV_FILE = Path.home() / ".omp" / "agent" / ".env"


class MissingTokenError(RuntimeError):
    """Raised when no Bedrock bearer token can be found."""


def load_bearer_token(env_file: Path = OMP_ENV_FILE) -> str:
    """Return the Bedrock bearer token.

    The environment variable wins. Otherwise the token is read from the ``.env``
    file that ``set-key`` writes for omp.

    Args:
        env_file: The ``.env`` file to fall back to.

    Returns:
        The bearer token.

    Raises:
        MissingTokenError: If neither the variable nor the file provides a token.
    """
    if token := os.environ.get(TOKEN_VARIABLE, "").strip():
        return token
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    for line in lines:
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and name.strip() == TOKEN_VARIABLE and value.strip():
            return value.strip().strip("'\"")
    raise MissingTokenError(
        f"Set {TOKEN_VARIABLE} or store the workshop key with set-key ({env_file})."
    )
