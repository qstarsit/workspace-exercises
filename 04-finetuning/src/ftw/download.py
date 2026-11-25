"""Download a base model into the Hugging Face cache ahead of time.

Example:
    uv run python -m ftw.download
    uv run python -m ftw.download --model HuggingFaceTB/SmolLM2-360M-Instruct
"""

import argparse
import logging

from huggingface_hub import snapshot_download

from ftw import configure_logging
from ftw.modeling import DEFAULT_BASE_MODEL

logger = logging.getLogger("ftw.download")


def main() -> None:
    """Download the model given on the command line."""
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=DEFAULT_BASE_MODEL)
    model = parser.parse_args().model
    path = snapshot_download(
        model, allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja"]
    )
    logger.info("%s is in %s", model, path)


if __name__ == "__main__":
    main()
