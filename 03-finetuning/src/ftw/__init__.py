"""Fine-tuning workshop: distil a large model into a small local one."""

import logging


def configure_logging() -> None:
    """Log this package at INFO and everything else at WARNING, without prefixes."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger(__name__).setLevel(logging.INFO)
