import pytest

from agent.registry import ToolError, ToolRegistry, json_type, parse_docstring


def make_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.register
    def greet(
        context: object, name: str, times: int = 1, loud: bool | None = None
    ) -> str:
        """Greet someone.

        Use this when asked to say hello.

        Args:
            name: Who to greet.
            times: How often to repeat
                the greeting.
            loud: Shout the greeting.

        Returns:
            The greeting.
        """
        greeting = f"hello {name}" * times
        return greeting.upper() if loud else greeting

    return registry


def test_spec_uses_function_name_and_docstring() -> None:
    spec = make_registry().specs[0]["toolSpec"]

    assert spec["name"] == "greet"
    assert spec["description"] == "Greet someone.\n\nUse this when asked to say hello."


def test_schema_is_generated_from_type_hints() -> None:
    schema = make_registry().specs[0]["toolSpec"]["inputSchema"]["json"]

    assert schema == {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Who to greet."},
            "times": {
                "type": "integer",
                "description": "How often to repeat the greeting.",
                "default": 1,
            },
            "loud": {"type": "boolean", "description": "Shout the greeting."},
        },
        "required": ["name"],
    }


def test_context_parameter_is_hidden_and_passed_through() -> None:
    registry = ToolRegistry()

    @registry.register
    def whoami(context: object) -> str:
        """Return the context."""
        return str(context)

    assert registry.specs[0]["toolSpec"]["inputSchema"]["json"]["properties"] == {}
    assert registry.run("whoami", {}, "ctx") == "ctx"


def test_run_calls_handler_with_arguments() -> None:
    result = make_registry().run("greet", {"name": "ada", "loud": True}, None)

    assert result == "HELLO ADA"


def test_unknown_tool_is_a_tool_error() -> None:
    with pytest.raises(ToolError, match=r"Unknown tool 'shout'\. Available: greet"):
        make_registry().run("shout", {}, None)


@pytest.mark.parametrize("arguments", [{}, {"name": "ada", "colour": "red"}])
def test_bad_arguments_are_a_tool_error(arguments: dict[str, str]) -> None:
    with pytest.raises(ToolError, match="Invalid arguments for greet"):
        make_registry().run("greet", arguments, None)


def test_duplicate_names_are_rejected() -> None:
    registry = make_registry()

    def greet(context: object) -> str:
        return ""

    with pytest.raises(ValueError, match="already registered"):
        registry.register(greet)


def test_unsupported_argument_type_is_rejected() -> None:
    def tagged(context: object, tags: list[str]) -> str:
        return ""

    with pytest.raises(TypeError, match="Unsupported tool argument type"):
        ToolRegistry().register(tagged)


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [(str, "string"), (int, "integer"), (float, "number"), (str | None, "string")],
)
def test_json_type(annotation: object, expected: str) -> None:
    assert json_type(annotation) == expected


def test_parse_docstring_without_args() -> None:
    assert parse_docstring("Just a summary.") == ("Just a summary.", {})
