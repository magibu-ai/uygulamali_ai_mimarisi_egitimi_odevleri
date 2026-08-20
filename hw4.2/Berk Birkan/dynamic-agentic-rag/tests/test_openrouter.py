from dynamic_rag.llm.openrouter import OpenRouterClient


class Response:
    def raise_for_status(self): pass
    def json(self):
        return {"data": [
            {"id": "free/model:free", "name": "Free Model", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "paid/model", "name": "Paid Model", "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
        ]}


class Client:
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get(self, *args, **kwargs): return Response()


def test_model_list_can_filter_free_models(monkeypatch):
    monkeypatch.setattr("dynamic_rag.llm.openrouter.httpx.Client", Client)
    choices = OpenRouterClient().list_models("key", free_only=True)
    values = [value for _, value in choices]
    assert values == ["openrouter/free", "free/model:free"]


def test_model_list_includes_paid_pricing(monkeypatch):
    monkeypatch.setattr("dynamic_rag.llm.openrouter.httpx.Client", Client)
    choices = OpenRouterClient().list_models("key", free_only=False)
    assert any(value == "paid/model" and "$1.00/$2.00" in label for label, value in choices)
