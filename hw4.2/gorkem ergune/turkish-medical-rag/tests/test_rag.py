"""Phase 7 tests: RAG threshold gate, LLM safety, context, prompt, pipeline.

Fully offline — fake embedder, fake store, fake LLM. No network/API calls.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.config import load_config
from src.rag.llm import FakeLLMClient, build_llm_client
from src.rag.pipeline import RAGPipeline
from src.rag.prompt import (
    SYSTEM_INSTRUCTIONS,
    build_context,
    build_prompt,
    build_sources,
    sort_chunks,
)

THRESHOLD = 0.575
REJECTION = "Bu sorunun cevabı dokümanlarımda yer almamaktadır"


# --- fakes ---------------------------------------------------------------- #

class FakeEmbedder:
    def encode_queries(self, questions):
        return np.zeros((len(questions), 1024), dtype=np.float32)


class FakeStore:
    """Returns preset hits (already in ranked order), truncated to top_k."""

    def __init__(self, hits):
        self._hits = hits

    def search(self, query_embedding, top_k):
        return self._hits[:top_k]


def _hit(cid, sim, parent="doc_1", title="Başlık", url="https://x", src="acibadem",
         text="tıbbi metin"):
    return {
        "chunk_id": cid, "similarity": sim, "parent_id": parent,
        "title": title, "url": url, "source": src, "chunk_text": text,
    }


def _pipeline(hits, llm=None, threshold=THRESHOLD, top_k=5):
    return RAGPipeline(
        embedder=FakeEmbedder(),
        store=FakeStore(hits),
        llm=llm or FakeLLMClient(),
        threshold=threshold,
        top_k=top_k,
        rejection_message=REJECTION,
        max_context_chars=6000,
    )


# --- threshold behaviour -------------------------------------------------- #

def test_below_threshold_rejected():
    llm = FakeLLMClient()
    result = _pipeline([_hit("c1", 0.50)], llm).answer("soru?")
    assert result["accepted"] is False
    assert result["answer"] == REJECTION
    assert result["llm_called"] is False
    assert llm.call_count == 0


def test_exactly_at_threshold_accepted():
    llm = FakeLLMClient()
    result = _pipeline([_hit("c1", THRESHOLD)], llm).answer("soru?")
    assert result["accepted"] is True
    assert result["llm_called"] is True
    assert llm.call_count == 1


def test_above_threshold_accepted():
    llm = FakeLLMClient()
    result = _pipeline([_hit("c1", 0.80)], llm).answer("soru?")
    assert result["accepted"] is True
    assert llm.call_count == 1


# --- LLM safety ----------------------------------------------------------- #

def test_rejected_query_never_calls_llm():
    llm = FakeLLMClient()
    _pipeline([_hit("c1", 0.10), _hit("c2", 0.05)], llm).answer("alakasız soru?")
    assert llm.call_count == 0


def test_accepted_query_calls_llm_exactly_once():
    llm = FakeLLMClient(answer="Cevap.")
    result = _pipeline([_hit("c1", 0.9), _hit("c2", 0.8)], llm).answer("soru?")
    assert llm.call_count == 1
    assert result["answer"] == "Cevap."


def test_empty_retrieval_is_rejected_without_llm():
    llm = FakeLLMClient()
    result = _pipeline([], llm).answer("soru?")
    assert result["accepted"] is False
    assert llm.call_count == 0
    assert result["top_similarity"] == 0.0


# --- context construction ------------------------------------------------- #

def test_context_sorted_by_similarity_desc():
    hits = [_hit("c1", 0.6, text="AAA"), _hit("c2", 0.9, text="BBB"),
            _hit("c3", 0.7, text="CCC")]
    ordered = sort_chunks(hits)
    assert [c["chunk_id"] for c in ordered] == ["c2", "c3", "c1"]


def test_context_contains_retrieved_text_and_metadata():
    hits = [_hit("c1", 0.9, title="Anemi", url="https://a", text="ANEMI_METNI")]
    ctx, used = build_context(hits, max_chars=6000)
    assert "ANEMI_METNI" in ctx
    assert "Anemi" in ctx and "https://a" in ctx
    assert len(used) == 1


def test_context_no_unrelated_chunks_added():
    hits = [_hit("c1", 0.9, text="ONLY_THIS")]
    ctx, used = build_context(hits, max_chars=6000)
    assert used == hits
    assert "UNRELATED" not in ctx


def test_context_respects_char_budget():
    hits = [_hit("c1", 0.9, text="x" * 500), _hit("c2", 0.8, text="y" * 5000)]
    _, used = build_context(hits, max_chars=800)
    assert [c["chunk_id"] for c in used] == ["c1"]  # second dropped by budget


def test_context_first_chunk_always_included():
    hits = [_hit("c1", 0.9, text="z" * 10000)]
    ctx, used = build_context(hits, max_chars=100)
    assert len(used) == 1 and "z" in ctx


# --- prompt design -------------------------------------------------------- #

def test_prompt_contains_question_context_and_grounding():
    system, user = build_prompt("Hastalık nedir?", "BAGLAM_METNI")
    assert "Hastalık nedir?" in user
    assert "BAGLAM_METNI" in user
    assert "RETRIEVED CONTEXT" in user and "USER QUESTION" in user
    # grounding + Turkish + only-from-context instructions live in system
    assert "yalnızca" in system.lower() or "yalnizca" in system.lower()
    assert "Türkçe" in system
    assert "Dış bilgi" in system or "dış bilgi" in system.lower()


def test_threshold_not_in_prompt():
    system, user = build_prompt("soru?", "baglam")
    assert "0.575" not in system and "0.575" not in user
    assert "threshold" not in user.lower()


# --- source attribution --------------------------------------------------- #

def test_sources_expose_only_real_metadata():
    used = [_hit("doc_1_chunk_000", 0.83, parent="doc_1", title="T", url="U")]
    sources = build_sources(used)
    assert sources[0] == {
        "chunk_id": "doc_1_chunk_000", "parent_id": "doc_1", "title": "T",
        "url": "U", "source": "acibadem", "similarity": 0.83,
    }


def test_accepted_result_exposes_sources_and_ids():
    hits = [_hit("c1", 0.9), _hit("c2", 0.8)]
    result = _pipeline(hits).answer("soru?")
    assert result["retrieved_chunk_ids"] == ["c1", "c2"]
    assert [s["chunk_id"] for s in result["sources"]] == ["c1", "c2"]


# --- config / factory ----------------------------------------------------- #

def test_config_has_llm_and_rag_sections():
    cfg = load_config()
    assert cfg["llm"]["model"]
    assert cfg["llm"]["api_key_env"] == "ANTHROPIC_API_KEY"
    assert isinstance(cfg["rag"]["max_context_chars"], int)
    assert cfg["rejection_message"].startswith("Bu sorunun cevabı")


def test_build_llm_client_fake_provider():
    cfg = load_config()
    cfg["llm"]["provider"] = "fake"
    client = build_llm_client(cfg)
    assert isinstance(client, FakeLLMClient)


def test_build_llm_client_unknown_provider_raises():
    cfg = load_config()
    cfg["llm"]["provider"] = "bogus"
    with pytest.raises(ValueError, match="provider"):
        build_llm_client(cfg)


# --- full flows ----------------------------------------------------------- #

def test_full_accepted_flow_with_fake_llm():
    llm = FakeLLMClient(answer="Anemi, kırmızı kan hücresi eksikliğidir.")
    hits = [_hit("doc_0_chunk_0", 0.72, title="Anemi", text="Anemi ... eksikliği")]
    result = _pipeline(hits, llm).answer("Anemi nedir?")
    assert result["accepted"] is True
    assert result["llm_called"] is True
    assert result["answer"] == "Anemi, kırmızı kan hücresi eksikliğidir."
    assert result["sources"][0]["title"] == "Anemi"
    assert llm.call_count == 1
    # the LLM saw the question and the grounded context
    assert "Anemi nedir?" in llm.calls[0]["user"]
    assert "Anemi ... eksikliği" in llm.calls[0]["user"]


def test_full_rejected_flow_asserts_zero_llm_calls():
    llm = FakeLLMClient()
    hits = [_hit("c1", 0.42), _hit("c2", 0.40)]  # all below threshold
    result = _pipeline(hits, llm).answer("Kleptomani nedir?")
    assert result["accepted"] is False
    assert result["answer"] == REJECTION
    assert result["llm_called"] is False
    assert llm.call_count == 0
    assert result["sources"] == []
    # eval hook still exposes what was retrieved
    assert result["retrieved_chunk_ids"] == ["c1", "c2"]
