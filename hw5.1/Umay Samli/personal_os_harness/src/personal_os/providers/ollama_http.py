"""Typed direct-HTTP adapter for Ollama chat and tool calling."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

import requests

from personal_os.config import OllamaSettings

Role = Literal["system", "user", "assistant", "tool"]


class OllamaError(RuntimeError):
    """Raised when Ollama cannot return a valid response."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Provider-neutral representation of one model-requested function call."""

    name: str
    arguments: Mapping[str, object]

    def as_payload(self) -> dict[str, object]:
        return {
            "function": {
                "name": self.name,
                "arguments": dict(self.arguments),
            }
        }


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """Validated chat message that can round-trip through Ollama."""

    role: Role
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str | None = None

    def __post_init__(self) -> None:
        if self.tool_calls and self.role != "assistant":
            raise ValueError("tool calls are allowed only on assistant messages")
        if self.role == "tool" and not self.tool_name:
            raise ValueError("tool messages require tool_name")
        if self.role != "tool" and self.tool_name is not None:
            raise ValueError("tool_name is allowed only on tool messages")

    def as_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_calls:
            payload["tool_calls"] = [tool_call.as_payload() for tool_call in self.tool_calls]
        if self.tool_name is not None:
            payload["tool_name"] = self.tool_name
        return payload


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Application-level chat result independent of Ollama response dictionaries."""

    message: ChatMessage

    @property
    def tool_calls(self) -> tuple[ToolCall, ...]:
        return self.message.tool_calls


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Capabilities advertised by the configured Ollama model."""

    model: str
    capabilities: frozenset[str]


class HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


class HttpSession(Protocol):
    def post(
        self,
        url: str,
        *,
        json: Mapping[str, object],
        timeout: int,
    ) -> HttpResponse: ...


class OllamaHttpClient:
    """Typed adapter around Ollama's direct chat and model-details endpoints."""

    def __init__(
        self,
        settings: OllamaSettings,
        session: HttpSession | None = None,
    ) -> None:
        self._settings = settings
        self._session: HttpSession = session or cast(HttpSession, requests.Session())

    def check_tool_support(self) -> ModelCapabilities:
        body = self._post(
            self._show_url(),
            {"model": self._settings.model},
        )
        raw_capabilities = body.get("capabilities")
        if not isinstance(raw_capabilities, list):
            raise OllamaError("Ollama model details are missing a valid capabilities list")
        capability_values = cast(list[object], raw_capabilities)
        if not all(isinstance(capability, str) for capability in capability_values):
            raise OllamaError("Ollama model details are missing a valid capabilities list")
        capabilities = frozenset(cast(list[str], capability_values))
        if "tools" not in capabilities:
            raise OllamaError(
                f"configured Ollama model {self._settings.model!r} does not advertise tool support"
            )
        return ModelCapabilities(self._settings.model, capabilities)

    def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[Mapping[str, object]] = (),
    ) -> ChatResponse:
        payload: dict[str, object] = {
            "model": self._settings.model,
            "messages": [message.as_payload() for message in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = [dict(tool) for tool in tools]

        body = self._post(self._settings.url, payload)
        raw_message = body.get("message")
        if not isinstance(raw_message, dict):
            raise OllamaError("Ollama response is missing a message object")
        message_object = cast(Mapping[str, object], raw_message)

        role = message_object.get("role")
        content = message_object.get("content")
        if role != "assistant" or not isinstance(content, str):
            raise OllamaError("Ollama returned an invalid assistant message")

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=content,
                tool_calls=_parse_tool_calls(message_object.get("tool_calls", [])),
            )
        )

    def _post(
        self,
        url: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=self._settings.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as error:
            raise OllamaError("Ollama request failed") from error

        # Provider payloads are untrusted input. Validate their shape here so no
        # Ollama-specific dictionaries escape into the agent or tool modules.
        if not isinstance(body, dict):
            raise OllamaError("Ollama returned a non-object response")
        return cast(Mapping[str, object], body)

    def _show_url(self) -> str:
        parsed = urlsplit(self._settings.url)
        if not parsed.path.endswith("/api/chat"):
            raise OllamaError("OLLAMA_URL must end with /api/chat")
        # Capability discovery is coupled to the same Ollama origin as chat; a
        # second configurable base URL could silently check a different server.
        show_path = f"{parsed.path[: -len('/chat')]}/show"
        return urlunsplit((parsed.scheme, parsed.netloc, show_path, "", ""))


def _parse_tool_calls(raw_tool_calls: object) -> tuple[ToolCall, ...]:
    if not isinstance(raw_tool_calls, list):
        raise OllamaError("Ollama returned invalid tool calls")

    parsed: list[ToolCall] = []
    for raw_tool_call in cast(list[object], raw_tool_calls):
        if not isinstance(raw_tool_call, dict):
            raise OllamaError("Ollama returned invalid tool calls")
        tool_call = cast(Mapping[str, object], raw_tool_call)
        raw_function = tool_call.get("function")
        if not isinstance(raw_function, dict):
            raise OllamaError("Ollama tool call is missing a function object")
        function = cast(Mapping[str, object], raw_function)
        name = function.get("name")
        arguments = function.get("arguments")
        if not isinstance(name, str) or not name.strip():
            raise OllamaError("Ollama tool call has an invalid function name")
        if not isinstance(arguments, dict):
            raise OllamaError("Ollama tool call has invalid arguments")
        argument_values = cast(dict[object, object], arguments)
        if not all(isinstance(key, str) for key in argument_values):
            raise OllamaError("Ollama tool call has invalid arguments")
        parsed.append(
            ToolCall(
                name=name,
                arguments=cast(Mapping[str, object], dict(argument_values)),
            )
        )
    return tuple(parsed)
