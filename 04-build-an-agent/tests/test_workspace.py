from pathlib import Path

import pytest

from agent.registry import ToolError
from agent.workspace import Workspace


def test_relative_path_resolves_inside_root(workspace: Workspace) -> None:
    resolved = workspace.resolve("src/pkg/core.py")

    assert resolved == workspace.root / "src" / "pkg" / "core.py"


def test_dot_resolves_to_root(workspace: Workspace) -> None:
    assert workspace.resolve(".") == workspace.root
    assert workspace.relative(workspace.root) == "."


@pytest.mark.parametrize("path", ["../secret.txt", "src/../../secret.txt", "/etc"])
def test_paths_outside_root_are_rejected(workspace: Workspace, path: str) -> None:
    with pytest.raises(ToolError, match="outside the workspace"):
        workspace.resolve(path)


def test_dotdot_that_stays_inside_is_allowed(workspace: Workspace) -> None:
    assert workspace.resolve("src/../README.md") == workspace.root / "README.md"


def test_symlink_pointing_outside_is_rejected(workspace: Workspace) -> None:
    (workspace.root / "escape").symlink_to(workspace.root.parent / "secret.txt")

    with pytest.raises(ToolError, match="outside the workspace"):
        workspace.resolve("escape")


def test_symlinked_directory_pointing_outside_is_rejected(
    workspace: Workspace,
) -> None:
    (workspace.root / "parent").symlink_to(workspace.root.parent)

    with pytest.raises(ToolError, match="outside the workspace"):
        workspace.resolve("parent/secret.txt")


def test_symlink_inside_root_is_allowed(workspace: Workspace) -> None:
    (workspace.root / "link.md").symlink_to(workspace.root / "README.md")

    assert workspace.resolve("link.md") == workspace.root / "README.md"


def test_root_is_resolved_through_symlinks(
    tmp_path: Path, workspace: Workspace
) -> None:
    alias = tmp_path / "alias"
    alias.symlink_to(workspace.root)

    assert Workspace(alias).root == workspace.root


def test_missing_root_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Workspace(tmp_path / "missing")


def test_file_as_root_is_an_error(tmp_path: Path) -> None:
    file = tmp_path / "file.txt"
    file.write_text("x")

    with pytest.raises(NotADirectoryError):
        Workspace(file)
