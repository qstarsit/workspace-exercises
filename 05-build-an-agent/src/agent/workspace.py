from pathlib import Path

from agent.registry import ToolError


class Workspace:
    """The directory the agent may touch; every path goes through ``resolve``."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise NotADirectoryError(self.root)

    def resolve(self, path: str) -> Path:
        """Turn a path from the model into an absolute path inside the workspace.

        Symlinks and ``..`` are resolved before the check, so neither can be used
        to step outside the root.

        Args:
            path: A path relative to the workspace root.

        Returns:
            The resolved absolute path.

        Raises:
            ToolError: If the path resolves to a location outside the workspace.
        """
        candidate = (self.root / path).resolve()
        if not candidate.is_relative_to(self.root):
            raise ToolError(f"{path} is outside the workspace")
        return candidate

    def relative(self, path: Path) -> str:
        """Show an absolute path inside the workspace relative to its root.

        Args:
            path: An absolute path inside the workspace.

        Returns:
            The POSIX-style relative path, or ``.`` for the root itself.
        """
        return path.relative_to(self.root).as_posix() or "."
