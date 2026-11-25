import pytest

from agent.registry import ToolError
from agent.tools import (
    MAX_LIST_ENTRIES,
    ToolContext,
    list_files,
    read_file,
    registry,
    truncate,
)


def test_registry_exposes_starter_tools() -> None:
    names = [spec["toolSpec"]["name"] for spec in registry.specs]

    assert names == ["list_files", "read_file"]


def test_list_files_shows_two_levels_and_skips_ignored(context: ToolContext) -> None:
    assert list_files(context).splitlines() == ["README.md", "src/", "src/pkg/"]


def test_list_files_depth_and_subdirectory(context: ToolContext) -> None:
    assert list_files(context, max_depth=1).splitlines() == ["README.md", "src/"]
    assert list_files(context, "src", max_depth=5).splitlines() == [
        "src/pkg/",
        "src/pkg/core.py",
    ]


def test_list_files_caps_entries(context: ToolContext) -> None:
    many = context.workspace.root / "many"
    many.mkdir()
    for index in range(MAX_LIST_ENTRIES + 5):
        (many / f"f{index:04}.txt").touch()

    lines = list_files(context, "many").splitlines()

    assert len(lines) == MAX_LIST_ENTRIES + 1
    assert lines[-1].startswith("[truncated")


def test_list_files_rejects_files_and_outside_paths(context: ToolContext) -> None:
    with pytest.raises(ToolError, match="not a directory"):
        list_files(context, "README.md")
    with pytest.raises(ToolError, match="outside the workspace"):
        list_files(context, "..")


def test_read_file_returns_content(context: ToolContext) -> None:
    assert read_file(context, "README.md") == "# Demo\nA demo project."


def test_read_file_pages_long_files(context: ToolContext) -> None:
    (context.workspace.root / "long.txt").write_text(
        "\n".join(f"line {n}" for n in range(1, 11))
    )

    page = read_file(context, "long.txt", start_line=3, max_lines=2)

    assert page == (
        "line 3\nline 4\n[showing lines 3-4 of 10; call again with start_line=5]"
    )


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("missing.txt", "Cannot read missing.txt"),
        ("src", "Cannot read src"),
        ("../secret.txt", "outside the workspace"),
    ],
)
def test_read_file_errors(context: ToolContext, path: str, message: str) -> None:
    with pytest.raises(ToolError, match=message):
        read_file(context, path)


def test_read_file_rejects_binary(context: ToolContext) -> None:
    (context.workspace.root / "blob.bin").write_bytes(b"\xff\xfe\x00")

    with pytest.raises(ToolError, match="not a UTF-8 text file"):
        read_file(context, "blob.bin")


def test_truncate() -> None:
    assert truncate("short", 10) == "short"
    assert truncate("abcdefghij", 4) == "abcd\n[truncated: 6 more characters]"
