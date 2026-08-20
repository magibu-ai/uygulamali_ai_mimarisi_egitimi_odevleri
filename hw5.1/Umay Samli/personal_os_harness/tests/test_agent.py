from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import cast

import pytest

from personal_os.agent import AgentRoundLimitError, PersonalOsAgent
from personal_os.db.postgres import DatabaseUnavailableError
from personal_os.providers.ollama_http import (
    ChatMessage,
    ChatResponse,
    ModelCapabilities,
    ToolCall,
)
from personal_os.tools import (
    RegisteredTool,
    ToolArgumentError,
    ToolDefinition,
    ToolRegistry,
)
from personal_os.tools.core import JsonValue, object_parameters


class FakeProvider:
    def __init__(self, responses: Sequence[ChatResponse]) -> None:
        self._responses = list(responses)
        self.check_count = 0
        self.calls: list[tuple[tuple[ChatMessage, ...], tuple[Mapping[str, object], ...]]] = []

    def check_tool_support(self) -> ModelCapabilities:
        self.check_count += 1
        return ModelCapabilities("test-model", frozenset({"tools"}))

    def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[Mapping[str, object]] = (),
    ) -> ChatResponse:
        self.calls.append((tuple(messages), tuple(tools)))
        return self._responses.pop(0)


def _tool(
    name: str,
    handler_result: JsonValue = "ok",
) -> RegisteredTool:
    def handler(arguments: Mapping[str, object]) -> JsonValue:
        return {
            "argument_count": len(arguments),
            "value": handler_result,
        }

    return RegisteredTool(
        ToolDefinition(name, "Test read tool.", object_parameters({})),
        handler,
    )


def _response(
    content: str,
    *tool_calls: ToolCall,
) -> ChatResponse:
    return ChatResponse(
        ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tuple(tool_calls),
        )
    )


def test_agent_executes_multiple_calls_and_preserves_complete_history() -> None:
    provider = FakeProvider(
        [
            _response(
                "",
                ToolCall("planning.first", {"value": 1}),
                ToolCall("memory.second", {"value": 2}),
            ),
            _response("I read both databases."),
        ]
    )
    agent = PersonalOsAgent(
        provider,
        ToolRegistry(
            (
                _tool("planning.first", "planning"),
                _tool("memory.second", "memory"),
            )
        ),
        max_tool_rounds=3,
        system_instructions="Use tools.",
    )

    turn = agent.run("What is relevant?")

    assert turn.content == "I read both databases."
    assert turn.tool_rounds == 1
    assert turn.tool_calls == (
        ToolCall("planning.first", {"value": 1}),
        ToolCall("memory.second", {"value": 2}),
    )
    assert provider.check_count == 1
    assert [message.role for message in turn.history] == [
        "system",
        "user",
        "assistant",
        "tool",
        "tool",
        "assistant",
    ]
    first_result = cast(dict[str, object], json.loads(turn.history[3].content))
    assert first_result["ok"] is True
    assert turn.history[3].tool_name == "planning.first"
    assert provider.calls[1][0][2].tool_calls == (
        ToolCall("planning.first", {"value": 1}),
        ToolCall("memory.second", {"value": 2}),
    )
    assert provider.calls[1][0][3].role == "tool"


def test_agent_capability_checks_only_once_across_turns() -> None:
    provider = FakeProvider([_response("First"), _response("Second")])
    agent = PersonalOsAgent(
        provider,
        ToolRegistry(()),
        max_tool_rounds=1,
    )

    agent.run("One")
    second = agent.run("Two")

    assert second.content == "Second"
    assert provider.check_count == 1
    assert [message.content for message in second.history if message.role == "user"] == [
        "One",
        "Two",
    ]


def test_agent_returns_invalid_arguments_as_a_tool_result() -> None:
    def invalid_handler(arguments: Mapping[str, object]) -> JsonValue:
        raise ToolArgumentError("limit must be at most 10")

    registry = ToolRegistry(
        (
            RegisteredTool(
                ToolDefinition(
                    "planning.invalid",
                    "Reject input.",
                    object_parameters({}),
                ),
                invalid_handler,
            ),
        )
    )
    provider = FakeProvider(
        [
            _response("", ToolCall("planning.invalid", {"limit": 11})),
            _response("Please use a smaller limit."),
        ]
    )

    turn = PersonalOsAgent(
        provider,
        registry,
        max_tool_rounds=2,
    ).run("Read too much")

    error_result = cast(dict[str, object], json.loads(turn.history[3].content))
    error = cast(dict[str, object], error_result["error"])
    assert error_result["ok"] is False
    assert error["code"] == "invalid_arguments"
    assert "at most 10" in cast(str, error["message"])


def test_agent_returns_database_outage_as_a_tool_result() -> None:
    def unavailable(arguments: Mapping[str, object]) -> JsonValue:
        raise DatabaseUnavailableError("planning database connection is unavailable")

    provider = FakeProvider(
        [
            _response("", ToolCall("planning.unavailable", {})),
            _response("The planning database is unavailable."),
        ]
    )
    registry = ToolRegistry(
        (
            RegisteredTool(
                ToolDefinition(
                    "planning.unavailable",
                    "Unavailable test tool.",
                    object_parameters({}),
                ),
                unavailable,
            ),
        )
    )

    turn = PersonalOsAgent(provider, registry, max_tool_rounds=2).run("Read")

    result = cast(dict[str, object], json.loads(turn.history[3].content))
    error = cast(dict[str, object], result["error"])
    assert error["code"] == "dependency_unavailable"


def test_agent_returns_unknown_tool_as_a_tool_result() -> None:
    provider = FakeProvider(
        [
            _response("", ToolCall("planning.missing", {})),
            _response("That tool is unavailable."),
        ]
    )

    turn = PersonalOsAgent(
        provider,
        ToolRegistry(()),
        max_tool_rounds=2,
    ).run("Use a missing tool")

    result = cast(dict[str, object], json.loads(turn.history[3].content))
    error = cast(dict[str, object], result["error"])
    assert error["code"] == "unknown_tool"


def test_agent_raises_after_configured_tool_round_limit() -> None:
    provider = FakeProvider(
        [
            _response("", ToolCall("planning.read", {})),
            _response("", ToolCall("planning.read", {})),
        ]
    )
    agent = PersonalOsAgent(
        provider,
        ToolRegistry((_tool("planning.read"),)),
        max_tool_rounds=1,
    )

    with pytest.raises(AgentRoundLimitError, match="1 tool-round"):
        agent.run("Keep reading")

    assert [message.role for message in agent.history] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
    ]


def test_agent_can_ask_clarification_without_executing_tools() -> None:
    provider = FakeProvider([_response("Which deadline should I use?")])
    agent = PersonalOsAgent(
        provider,
        ToolRegistry((_tool("planning.read"),)),
        max_tool_rounds=2,
    )

    turn = agent.run("Plan it")

    assert turn.content == "Which deadline should I use?"
    assert turn.tool_rounds == 0
    assert all(message.role != "tool" for message in turn.history)


@pytest.mark.parametrize("value", ["", "   "])
def test_agent_rejects_empty_user_content(value: str) -> None:
    agent = PersonalOsAgent(
        FakeProvider([]),
        ToolRegistry(()),
        max_tool_rounds=1,
    )

    with pytest.raises(ValueError, match="user_content"):
        agent.run(value)
