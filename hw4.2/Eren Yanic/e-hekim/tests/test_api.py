"""End-to-end HTTP behaviour, with the model and vector store stubbed out.

These tests are where the security claims meet the wire: that the keyless path
really is keyless, that the LLM is never reached below the threshold, and that
a credential cannot come back out in a response body.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ehekim import api, llm
from ehekim.config import MODEL_REFUSAL_MESSAGE_TR, REFUSAL_MESSAGE_TR
from ehekim.vectorstore import SearchHit

GOOD_KEY = "sk-abcdef0123456789abcdef0123456789"


def make_hit(similarity: float, chunk_id: str = "c1") -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        chunk_text="Migren, zonklayıcı baş ağrısıdır.",
        similarity=similarity,
        url="https://hastane.test/migren",
        title="Migren Nedir?",
        source="acibadem",
        parent_id="p1",
        chunk_index=0,
    )


class FakeEmbedder:
    device = "cpu"

    def encode_query(self, query: str) -> np.ndarray:
        return np.ones(8, dtype=np.float32)


class FakeStore:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits

    def count(self) -> int:
        return len(self.hits)

    def query(self, embedding, top_k: int) -> list[SearchHit]:
        return list(self.hits[:top_k])

    def get_siblings(self, parent_id: str, indices) -> list[SearchHit]:
        wanted = set(indices)
        return [
            h for h in self.hits
            if h.parent_id == parent_id and h.chunk_index in wanted
        ]


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """A client with app state injected directly, bypassing model loading."""
    monkeypatch.setattr(api.state, "embedder", FakeEmbedder(), raising=False)
    monkeypatch.setattr(
        api.state, "store", FakeStore([make_hit(0.82), make_hit(0.31, "c2")]), raising=False
    )
    # Not used as a context manager: lifespan (which loads the real model) is
    # deliberately not run.
    return TestClient(api.app)


class TestConfig:
    def test_exposes_catalogue_and_defaults(self, client):
        body = client.get("/api/config").json()
        assert body["embedding_dim"] == 768
        assert body["refusal_message"] == REFUSAL_MESSAGE_TR
        assert body["chunk_count"] == 2
        providers = {p["id"] for p in body["providers"]}
        assert "deepseek" in providers and "openrouter" in providers

    def test_catalogue_contains_no_credentials(self, client):
        """The catalogue ships key *hints* ("sk-…") but never a real key."""
        from ehekim.security import contains_secret

        raw = client.get("/api/config").text
        assert contains_secret(raw) is False

    def test_offers_more_than_one_model_family(self, client):
        body = client.get("/api/config").json()
        families = {m["family"] for p in body["providers"] for m in p["models"]}
        assert len(families) >= 3


class TestSecurityHeaders:
    def test_sets_hardening_headers(self, client):
        response = client.get("/api/health")
        assert "default-src 'self'" in response.headers["content-security-policy"]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"

    def test_rejects_oversized_bodies(self, client):
        response = client.post(
            "/api/search",
            content=b"x" * (api.MAX_BODY_BYTES + 1),
            headers={"Content-Type": "application/json", "Content-Length": str(api.MAX_BODY_BYTES + 1)},
        )
        assert response.status_code == 413


class TestSemanticSearch:
    def test_returns_similarities_and_partitions_on_the_threshold(self, client):
        body = client.post("/api/search", json={"query": "migren", "top_k": 5, "threshold": 0.55}).json()
        assert body["mode"] == "search"
        assert body["grounded"] is True
        assert body["best_similarity"] == pytest.approx(0.82)
        passed = [r for r in body["results"] if r["passed_threshold"]]
        rejected = [r for r in body["results"] if not r["passed_threshold"]]
        assert len(passed) == 1 and len(rejected) == 1
        assert passed[0]["similarity"] == pytest.approx(0.82)

    def test_needs_no_api_key(self, client):
        assert client.post("/api/search", json={"query": "migren"}).status_code == 200

    def test_high_threshold_yields_the_refusal_notice(self, client):
        body = client.post("/api/search", json={"query": "migren", "threshold": 0.95}).json()
        assert body["grounded"] is False
        assert body["notice"] == REFUSAL_MESSAGE_TR

    @pytest.mark.parametrize(
        "payload",
        [
            {"query": ""},
            {"query": "x", "top_k": 0},
            {"query": "x", "top_k": 999},
            {"query": "x", "threshold": 1.5},
            {"query": "x", "threshold": -0.1},
            {"query": "x", "unexpected": "field"},
        ],
    )
    def test_rejects_invalid_payloads(self, client, payload):
        assert client.post("/api/search", json=payload).status_code == 422


class TestRagAuth:
    def test_missing_key_is_rejected(self, client):
        assert client.post("/api/ask", json={"query": "migren"}).status_code == 401

    def test_malformed_key_is_rejected(self, client):
        response = client.post(
            "/api/ask", json={"query": "migren"}, headers={"X-Provider-Key": "short"}
        )
        assert response.status_code == 401

    def test_rejection_message_does_not_echo_the_key(self, client):
        secret = "sk-thisisaverysecretkey0123456789"
        response = client.post(
            "/api/ask", json={"query": "migren"}, headers={"X-Provider-Key": secret + " bad"}
        )
        assert secret not in response.text


class TestThresholdGateBlocksTheModel:
    def test_below_threshold_the_llm_is_never_called(self, client, monkeypatch):
        def explode(**kwargs):
            raise AssertionError("Eşiğin altında LLM çağrılmamalıydı.")

        monkeypatch.setattr(llm, "generate", explode)
        body = client.post(
            "/api/ask",
            json={"query": "ay'a nasıl gidilir", "threshold": 0.95},
            headers={"X-Provider-Key": GOOD_KEY},
        ).json()
        assert body["refused"] is True
        assert body["grounded"] is False
        assert body["answer"] == REFUSAL_MESSAGE_TR
        assert body["refusal_reason"] == "below_threshold"
        assert body["model"] is None

    def test_model_refusal_is_reported_as_the_second_layer(self, client, monkeypatch):
        """Passages cleared the gate, but the model said the answer is not there."""
        monkeypatch.setattr(
            llm,
            "generate",
            lambda **kw: llm.LLMResult(content=MODEL_REFUSAL_MESSAGE_TR, model="deepseek-v4-flash"),
        )
        body = client.post(
            "/api/ask",
            json={"query": "Hodgkin lenfomada sağkalım oranı nedir?", "threshold": 0.5},
            headers={"X-Provider-Key": GOOD_KEY},
        ).json()
        assert body["grounded"] is True          # retrieval did find close passages
        assert body["refused"] is True           # but the model declined
        assert body["refusal_reason"] == "model_insufficient_context"
        assert body["answer"] == MODEL_REFUSAL_MESSAGE_TR

    def test_empty_completion_becomes_a_refusal_not_an_empty_answer(self, client, monkeypatch):
        monkeypatch.setattr(
            llm, "generate", lambda **kw: llm.LLMResult(content="", model="m")
        )
        body = client.post(
            "/api/ask", json={"query": "migren", "threshold": 0.5},
            headers={"X-Provider-Key": GOOD_KEY},
        ).json()
        assert body["refused"] is True
        assert body["answer"] == MODEL_REFUSAL_MESSAGE_TR


class TestRagSuccess:
    def test_answers_and_forwards_the_key_without_returning_it(self, client, monkeypatch):
        seen = {}

        def fake_generate(*, model_key, api_key, messages, timeout, **kwargs):
            seen["model_key"] = model_key
            seen["api_key"] = api_key
            return llm.LLMResult(
                content="Migren zonklayıcı bir baş ağrısıdır [1].",
                model="deepseek-v4-flash",
                reasoning="gizli düşünce",
                prompt_tokens=100,
                completion_tokens=20,
                reasoning_tokens=5,
            )

        monkeypatch.setattr(llm, "generate", fake_generate)
        response = client.post(
            "/api/ask",
            json={"query": "migren nedir", "threshold": 0.5},
            headers={"X-Provider-Key": GOOD_KEY},
        )
        body = response.json()

        assert seen["api_key"] == GOOD_KEY          # forwarded upstream
        assert GOOD_KEY not in response.text        # never returned to the client
        assert body["refused"] is False
        assert body["answer"].startswith("Migren")
        assert body["usage"]["reasoning_tokens"] == 5

    def test_reasoning_is_withheld_unless_requested(self, client, monkeypatch):
        monkeypatch.setattr(
            llm,
            "generate",
            lambda **kw: llm.LLMResult(content="yanıt", model="m", reasoning="gizli"),
        )
        off = client.post(
            "/api/ask", json={"query": "migren", "threshold": 0.5},
            headers={"X-Provider-Key": GOOD_KEY},
        ).json()
        assert off["reasoning"] is None

        on = client.post(
            "/api/ask",
            json={"query": "migren", "threshold": 0.5, "include_reasoning": True},
            headers={"X-Provider-Key": GOOD_KEY},
        ).json()
        assert on["reasoning"] == "gizli"

    def test_upstream_errors_are_sanitised_before_relay(self, client, monkeypatch):
        def failing(**kwargs):
            raise llm.LLMError(
                f"Authentication Fails, Your api key: {GOOD_KEY} is invalid", status_code=401
            )

        monkeypatch.setattr(llm, "generate", failing)
        response = client.post(
            "/api/ask", json={"query": "migren", "threshold": 0.5},
            headers={"X-Provider-Key": GOOD_KEY},
        )
        assert response.status_code == 401
        assert GOOD_KEY not in response.text
        assert "REDACTED" in response.text


class TestLogRedaction:
    """The scrubber must clean strings without breaking record formatting."""

    def _record(self, msg, args):
        import logging

        return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, msg, args, None)

    def test_scrubs_credentials_from_message_args(self):
        record = self._record("key=%s", (f"Bearer {GOOD_KEY}",))
        api.RedactingFilter().filter(record)
        assert GOOD_KEY not in record.getMessage()
        assert "REDACTED" in record.getMessage()

    def test_preserves_numeric_args_so_uvicorn_access_log_still_formats(self):
        """Regression: coercing args to str made '%d' raise on the status code."""
        record = self._record(
            '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:1234", "POST", "/api/ask", "1.1", 413)
        )
        api.RedactingFilter().filter(record)
        assert record.getMessage() == '127.0.0.1:1234 - "POST /api/ask HTTP/1.1" 413'

    def test_handles_dict_args(self):
        record = self._record("%(k)s %(n)d", {"k": f"sk-{'a1b2c3d4' * 4}", "n": 7})
        api.RedactingFilter().filter(record)
        assert record.args["n"] == 7


class TestModelCatalogue:
    def test_unknown_model_key_is_a_client_error(self):
        with pytest.raises(llm.LLMError) as info:
            llm.get_model_spec("bogus:model")
        assert info.value.status_code == 400

    def test_deepseek_default_enables_thinking(self):
        spec = llm.get_model_spec(None)
        assert spec.model == "deepseek-v4-flash"
        assert spec.supports_thinking is True
