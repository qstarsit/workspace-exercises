import inspect
import re
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Union, get_args, get_origin, get_type_hints

from agent.model import JsonObject

type ToolHandler = Callable[..., str]

JSON_TYPES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}
ARG_LINE = re.compile(r"^\s{4}(\w+)(?: \(.*\))?:\s*(.*)$")


class ToolError(Exception):
    """A failure the model should see and can recover from, e.g. a bad path."""


@dataclass(frozen=True)
class Tool:
    """A tool the model can call.

    Attributes:
        name: Name the model uses to call the tool.
        description: What the tool does and when to use it.
        input_schema: JSON schema of the arguments.
        handler: Function that runs the tool. Its first parameter receives the
            tool context; the remaining parameters are the arguments.
    """

    name: str
    description: str
    input_schema: JsonObject
    handler: ToolHandler

    @property
    def spec(self) -> JsonObject:
        """The tool in Converse ``toolSpec`` format."""
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.description,
                "inputSchema": {"json": self.input_schema},
            }
        }


class ToolRegistry:
    """Collects tools and dispatches tool calls from the model to them."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, handler: ToolHandler) -> ToolHandler:
        """Register a function as a tool; usable as a decorator.

        The name comes from the function name, the description and argument
        descriptions from its Google-style docstring, and the JSON schema from
        its type hints. The first parameter (the tool context) is hidden from
        the model.

        Args:
            handler: The tool function.

        Returns:
            The same function, unchanged.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if handler.__name__ in self._tools:
            raise ValueError(f"Tool {handler.__name__} is already registered")
        description, arg_descriptions = parse_docstring(inspect.getdoc(handler) or "")
        self._tools[handler.__name__] = Tool(
            name=handler.__name__,
            description=description,
            input_schema=build_input_schema(handler, arg_descriptions),
            handler=handler,
        )
        return handler

    @property
    def specs(self) -> list[JsonObject]:
        """All tools in Converse ``toolSpec`` format."""
        return [tool.spec for tool in self._tools.values()]

    def run(self, name: str, arguments: JsonObject, context: object) -> str:
        """Run a tool call from the model.

        Args:
            name: The tool name the model asked for.
            arguments: The arguments the model supplied.
            context: Passed to the handler as its first argument.

        Returns:
            The tool output.

        Raises:
            ToolError: If the tool is unknown, the arguments do not match its
                signature, or the tool itself reports a failure.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(
                f"Unknown tool {name!r}. Available: {', '.join(self._tools)}"
            )
        try:
            bound = inspect.signature(tool.handler).bind(context, **arguments)
        except TypeError as error:
            raise ToolError(f"Invalid arguments for {name}: {error}") from error
        return tool.handler(*bound.args, **bound.kwargs)


def parse_docstring(docstring: str) -> tuple[str, dict[str, str]]:
    """Split a Google-style docstring into a description and argument docs.

    Args:
        docstring: The cleaned docstring (``inspect.getdoc``).

    Returns:
        The text before the first section, and a mapping of argument name to
        description taken from the ``Args:`` section.
    """
    summary, _, sections = docstring.partition("\nArgs:\n")
    arg_descriptions: dict[str, str] = {}
    current: str | None = None
    for line in sections.splitlines():
        if line and not line.startswith(" "):
            break
        if match := ARG_LINE.match(line):
            current = match.group(1)
            arg_descriptions[current] = match.group(2)
        elif current and line.strip():
            arg_descriptions[current] += f" {line.strip()}"
    return summary.strip(), arg_descriptions


def build_input_schema(
    handler: ToolHandler, arg_descriptions: dict[str, str]
) -> JsonObject:
    """Derive a JSON schema for a tool's arguments from its signature.

    Args:
        handler: The tool function. Its first parameter is skipped.
        arg_descriptions: Argument descriptions to include in the schema.

    Returns:
        A JSON schema object with ``properties`` and ``required``.

    Raises:
        TypeError: If an argument has a type that has no JSON equivalent.
    """
    hints = get_type_hints(handler)
    parameters = list(inspect.signature(handler).parameters.values())[1:]
    properties: JsonObject = {}
    required: list[str] = []
    for parameter in parameters:
        schema: JsonObject = {"type": json_type(hints[parameter.name])}
        if parameter.name in arg_descriptions:
            schema["description"] = arg_descriptions[parameter.name]
        if parameter.default is inspect.Parameter.empty:
            required.append(parameter.name)
        elif parameter.default is not None:
            schema["default"] = parameter.default
        properties[parameter.name] = schema
    return {"type": "object", "properties": properties, "required": required}


def json_type(annotation: object) -> str:
    """Map a Python type hint to a JSON schema type name.

    Args:
        annotation: A type hint such as ``str`` or ``int | None``.

    Returns:
        The JSON schema type, e.g. ``string``.

    Raises:
        TypeError: If the hint has no JSON equivalent.
    """
    if get_origin(annotation) in (Union, types.UnionType):
        members = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(members) == 1:
            return json_type(members[0])
    if isinstance(annotation, type) and annotation in JSON_TYPES:
        return JSON_TYPES[annotation]
    raise TypeError(f"Unsupported tool argument type: {annotation!r}")
