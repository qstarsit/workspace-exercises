import os
from dataclasses import dataclass
from pathlib import Path

from agent.registry import ToolError, ToolRegistry
from agent.workspace import Workspace

IGNORED_DIRECTORIES = frozenset(
    {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)
MAX_LIST_ENTRIES = 300
MAX_OUTPUT_CHARS = 20_000

registry = ToolRegistry()


@dataclass(frozen=True)
class ToolContext:
    """What every tool receives as its first argument.

    Attributes:
        workspace: The directory the agent is confined to.
    """

    workspace: Workspace


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Cut text to a size the model can take, and say that it was cut.

    Args:
        text: The tool output.
        limit: Maximum number of characters to keep.

    Returns:
        The text, or its first ``limit`` characters plus a note.
    """
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n[truncated: {len(text) - limit} more characters]"


@registry.register
def list_files(context: ToolContext, path: str = ".", max_depth: int = 2) -> str:
    """List files and directories in the workspace. Directories end with '/'.

    Args:
        context: The tool context.
        path: Directory to list, relative to the workspace root.
        max_depth: How many levels to descend; 1 lists only direct children.
    """
    directory = context.workspace.resolve(path)
    if not directory.is_dir():
        raise ToolError(f"{path} is not a directory")
    entries: list[str] = []
    for current, dirnames, filenames in os.walk(directory):
        base = Path(current)
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRECTORIES]
        entries.extend(f"{context.workspace.relative(base / d)}/" for d in dirnames)
        entries.extend(context.workspace.relative(base / f) for f in filenames)
        if len(base.relative_to(directory).parts) + 1 >= max_depth:
            dirnames.clear()
        if len(entries) > MAX_LIST_ENTRIES:
            break
    if not entries:
        return f"{path} is empty"
    entries.sort()
    if len(entries) > MAX_LIST_ENTRIES:
        entries[MAX_LIST_ENTRIES:] = [
            "[truncated: list a subdirectory or lower max_depth]"
        ]
    return "\n".join(entries)


@registry.register
def read_file(
    context: ToolContext, path: str, start_line: int = 1, max_lines: int = 400
) -> str:
    """Read a UTF-8 text file from the workspace.

    Args:
        context: The tool context.
        path: File to read, relative to the workspace root.
        start_line: First line to return, counting from 1.
        max_lines: Maximum number of lines to return.
    """
    file = context.workspace.resolve(path)
    try:
        lines = file.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ToolError(f"Cannot read {path}: {error.strerror}") from error
    except UnicodeDecodeError as error:
        raise ToolError(f"{path} is not a UTF-8 text file") from error
    first = max(start_line, 1) - 1
    selected = lines[first : first + max_lines]
    text = "\n".join(selected)
    if first + len(selected) < len(lines):
        last = first + len(selected)
        text += (
            f"\n[showing lines {first + 1}-{last} of {len(lines)};"
            f" call again with start_line={last + 1}]"
        )
    return truncate(text)
