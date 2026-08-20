"""Provider-neutral declarations, dispatch, and result serialization for tools."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, time
from typing import Protocol, TypeAlias, cast
from uuid import UUID

from personal_os.db.postgres import DatabaseUnavailableError

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class ToolNotFoundError(LookupError):
    """Raised when a model requests a tool that is not registered."""


class ToolExecutionError(RuntimeError):
    """Raised when a registered tool cannot reach its required dependency."""


class ToolHandler(Protocol):
    """Callable interface implemented by a bounded tool adapter."""

    def __call__(self, arguments: Mapping[str, object]) -> JsonValue: ...


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Provider-neutral function declaration with JSON Schema parameters."""

    name: str
    description: str
    parameters: JsonObject

    def as_ollama_tool(self) -> JsonObject:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """Pair one public declaration with its executable adapter."""

    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    """Resolve declared tools by exact name and execute their typed adapters."""

    def __init__(self, tools: Iterable[RegisteredTool]) -> None:
        registered: dict[str, RegisteredTool] = {}
        for tool in tools:
            name = tool.definition.name
            if name in registered:
                raise ValueError(f"duplicate tool name: {name}")
            registered[name] = tool
        self._tools = registered

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition for tool in self._tools.values())

    def as_ollama_tools(self) -> list[JsonObject]:
        return [definition.as_ollama_tool() for definition in self.definitions]

    def execute(self, name: str, arguments: Mapping[str, object]) -> JsonValue:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(f"unknown tool: {name}")
        try:
            return tool.handler(arguments)
        except DatabaseUnavailableError as error:
            raise ToolExecutionError(str(error)) from error


def object_parameters(
    properties: JsonObject,
    *,
    required: tuple[str, ...] = (),
) -> JsonObject:
    schema: JsonObject = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = list(required)
    return schema


def database_result(source: str, data: JsonValue) -> JsonObject:
    """Label database output so the model cannot confuse planning and memory."""
    return {"source": source, "data": data}


def collection_result(
    source: str,
    records: tuple[object, ...],
    *,
    limit: int,
    offset: int | None = None,
) -> JsonObject:
    data: JsonObject = {
        "items": [to_json_value(record) for record in records],
        "count": len(records),
        "limit": limit,
    }
    if offset is not None:
        data["offset"] = offset
    return database_result(source, data)


def item_result(source: str, record: object | None) -> JsonObject:
    return database_result(
        source,
        {
            "found": record is not None,
            "item": to_json_value(record),
        },
    )


def to_json_value(value: object) -> JsonValue:
    """Convert typed records and standard temporal/UUID values to JSON-safe data."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_json_value(cast(object, getattr(value, field.name)))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        converted: JsonObject = {}
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            converted[key] = to_json_value(item)
        return converted
    if isinstance(value, list | tuple):
        values = cast(list[object] | tuple[object, ...], value)
        return [to_json_value(item) for item in values]
    raise TypeError(f"cannot convert {type(value).__name__} to JSON")
