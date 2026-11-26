import argparse
import logging
import os
from pathlib import Path

from agent.config import (
    DEFAULT_MODEL_ID,
    DEFAULT_REGION,
    MissingTokenError,
    load_bearer_token,
)
from agent.console import ConsoleReporter
from agent.loop import Agent
from agent.model import ModelError, create_bedrock_client
from agent.tools import ToolContext, registry
from agent.workspace import Workspace

logger = logging.getLogger("agent")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog="agent", description="A minimal coding agent on Amazon Bedrock."
    )
    parser.add_argument("task", help="what the agent should do")
    parser.add_argument(
        "--workspace", type=Path, default=Path(), help="directory the agent may use"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL_ID, help="Bedrock model ID")
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", DEFAULT_REGION),
        help="AWS region (default: $AWS_REGION or eu-north-1)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the agent on one task and print every step.

    Args:
        argv: Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns:
        The process exit code.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        workspace = Workspace(args.workspace)
        client = create_bedrock_client(load_bearer_token(), args.region, args.model)
    except (OSError, MissingTokenError) as error:
        logger.error("%s", error)
        return 1
    agent = Agent(client, registry, ToolContext(workspace), ConsoleReporter())
    try:
        agent.run(args.task)
    except ModelError as error:
        logger.error("%s", error)
        return 1
    except KeyboardInterrupt:
        logger.error("Interrupted")
        return 130
    return 0
