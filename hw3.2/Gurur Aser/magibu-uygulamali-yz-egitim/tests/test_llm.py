from odev2_beehive_assistant.llm import MAX_COMPLETION_TOKENS, HFRouterClient


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}


class FakeSDK:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


def test_router_request_has_finite_retry_timeout_and_completion_cap():
    assert MAX_COMPLETION_TOKENS == 4096
    sdk = FakeSDK()
    result = HFRouterClient(client=sdk, max_tokens=MAX_COMPLETION_TOKENS * 5).complete(
        [{"role": "user", "content": "merhaba"}], [], tool_choice="required"
    )
    assert result["content"] == "ok"
    assert sdk.chat.completions.kwargs["max_tokens"] == MAX_COMPLETION_TOKENS
    assert sdk.chat.completions.kwargs["tool_choice"] == "required"
