from collections.abc import Mapping, Sequence
from typing import cast

import pytest

from personal_os.config import OllamaSettings
from personal_os.providers.ollama_http import (
    ChatMessage,
    OllamaError,
    OllamaHttpClient,
    ToolCall,
)


class FakeResponse:
    def __init__(self, body: object) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._body


class FakeSession:
    def __init__(self, bodies: Sequence[object]) -> None:
        self._bodies = list(bodies)
        self.requests: list[tuple[str, Mapping[str, object], int]] = []

    def post(
        self,
        url: str,
        *,
        json: Mapping[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.requests.append((url, json, timeout))
        return FakeResponse(self._bodies.pop(0))


class TimeoutSession:
    def post(
        self,
        url: str,
        *,
        json: Mapping[str, object],
        timeout: int,
    ) -> FakeResponse:
        import requests

        raise requests.Timeout("timed out")


def _settings() -> OllamaSettings:
    return OllamaSettings(
        model="qwen3:8b",
        url="http://localhost:11434/api/chat",
        timeout_seconds=30,
        max_tool_rounds=5,
    )


def test_chat_sends_tools_and_returns_typed_tool_call() -> None:
    call_body: object = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "planning.get_settings",
                        "arguments": cast(Mapping[str, object], {}),
                    }
                }
            ],
        }
    }
    session = FakeSession([call_body])
    client = OllamaHttpClient(_settings(), session)
    declaration: Mapping[str, object] = {
        "type": "function",
        "function": {"name": "planning.get_settings"},
    }

    result = client.chat(
        [ChatMessage(role="user", content="Show settings")],
        [declaration],
    )

    assert result.message == ChatMessage(
        role="assistant",
        content="",
        tool_calls=(ToolCall("planning.get_settings", {}),),
    )
    payload = session.requests[0][1]
    assert payload["stream"] is False
    assert payload["tools"] == [dict(declaration)]
    assert session.requests[0][2] == 30


def test_chat_preserves_assistant_calls_and_named_tool_results_in_history() -> None:
    session = FakeSession([{"message": {"role": "assistant", "content": "Done."}}])
    call = ToolCall("planning.get_settings", {})
    messages = [
        ChatMessage(role="assistant", content="", tool_calls=(call,)),
        ChatMessage(
            role="tool",
            content='{"source":"planning_database"}',
            tool_name=call.name,
        ),
    ]

    OllamaHttpClient(_settings(), session).chat(messages, [])

    assert session.requests[0][1]["messages"] == [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "planning.get_settings",
                        "arguments": {},
                    }
                }
            ],
        },
        {
            "role": "tool",
            "content": '{"source":"planning_database"}',
            "tool_name": "planning.get_settings",
        },
    ]


def test_check_tool_support_uses_show_endpoint() -> None:
    session = FakeSession([{"capabilities": ["completion", "tools"]}])

    result = OllamaHttpClient(_settings(), session).check_tool_support()

    assert result.model == "qwen3:8b"
    assert result.capabilities == frozenset({"completion", "tools"})
    assert session.requests[0][0] == "http://localhost:11434/api/show"
    assert session.requests[0][1] == {"model": "qwen3:8b"}


def test_check_tool_support_rejects_incapable_model() -> None:
    session = FakeSession([{"capabilities": ["completion"]}])

    with pytest.raises(OllamaError, match="does not advertise tool support"):
        OllamaHttpClient(_settings(), session).check_tool_support()


_MALFORMED_BODIES: list[object] = [
    {"message": "wrong"},
    {"message": {"role": "assistant", "content": "", "tool_calls": {}}},
    {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "", "arguments": {}}}],
        }
    },
    {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "planning.get_settings",
                        "arguments": [],
                    }
                }
            ],
        }
    },
]


@pytest.mark.parametrize("body", _MALFORMED_BODIES)
def test_chat_rejects_malformed_responses(body: object) -> None:
    with pytest.raises(OllamaError):
        OllamaHttpClient(_settings(), FakeSession([body])).chat([])


def test_chat_normalizes_request_timeout() -> None:
    with pytest.raises(OllamaError, match="request failed"):
        OllamaHttpClient(_settings(), TimeoutSession()).chat([])


def test_chat_message_enforces_tool_history_shape() -> None:
    with pytest.raises(ValueError, match="assistant"):
        ChatMessage(
            role="user",
            content="bad",
            tool_calls=(ToolCall("planning.get_settings", {}),),
        )
    with pytest.raises(ValueError, match="require tool_name"):
        ChatMessage(role="tool", content="{}")
