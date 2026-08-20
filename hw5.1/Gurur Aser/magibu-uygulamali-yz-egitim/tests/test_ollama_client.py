from __future__ import annotations

from dataclasses import dataclass

from les8.ollama_client import MODEL, MODEL_OPTIONS, OllamaClient


class FakeChat:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class FakeSDK:
    def __init__(self, response):
        self.chat = FakeChat(response)


def test_client_sends_local_model_options_and_normalizes_mapping_response():
    response = {
        "message": {
            "role": "assistant",
            "content": "Envanterini kontrol ediyorum.",
            "tool_calls": [
                {
                    "function": {
                        "name": "list_pantry",
                        "arguments": {"expiring_within_days": 7},
                    }
                }
            ],
        }
    }
    sdk = FakeSDK(response)
    client = OllamaClient(client=sdk)

    result = client.complete([{"role": "user", "content": "Dolabımı kontrol et"}], [{"type": "function"}])

    assert client.model == MODEL == "qwen3.5:9b-q4_K_M"
    assert result["role"] == "assistant"
    assert result["tool_calls"][0]["function"]["name"] == "list_pantry"
    assert result["tool_calls"][0]["function"]["arguments"] == {"expiring_within_days": 7}
    assert sdk.chat.kwargs["model"] == MODEL
    assert sdk.chat.kwargs["stream"] is False
    assert sdk.chat.kwargs["think"] is False
    assert sdk.chat.kwargs["options"] == MODEL_OPTIONS
    assert sdk.chat.kwargs["messages"] == [{"role": "user", "content": "Dolabımı kontrol et"}]


@dataclass
class FakeFunction:
    name: str
    arguments: dict


@dataclass
class FakeToolCall:
    function: FakeFunction


@dataclass
class FakeMessage:
    role: str
    content: str
    tool_calls: list


@dataclass
class FakeResponse:
    message: FakeMessage


def test_client_normalizes_ollama_pydantic_like_objects_without_call_id_assumptions():
    response = FakeResponse(
        FakeMessage(
            role="assistant",
            content="",
            tool_calls=[FakeToolCall(FakeFunction("internet_search", {"query": "mercimek tarifi"}))],
        )
    )
    sdk = FakeSDK(response)
    result = OllamaClient(client=sdk).complete([], [])

    assert result == {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "internet_search", "arguments": {"query": "mercimek tarifi"}}}],
    }


def test_client_close_delegates_when_sdk_exposes_close():
    sdk = FakeSDK({"message": {"role": "assistant", "content": "ok"}})
    closed = []
    sdk.close = lambda: closed.append(True)
    client = OllamaClient(client=sdk)

    client.close()

    assert closed == [True]
