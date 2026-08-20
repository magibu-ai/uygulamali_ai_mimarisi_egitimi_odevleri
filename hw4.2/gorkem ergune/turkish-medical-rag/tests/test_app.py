"""Web UI logic smoke tests — offline (no streamlit, no model/DB/LLM)."""
from __future__ import annotations

import importlib

from src.rag.llm import FakeLLMClient

app_logic = importlib.import_module("scripts.app_logic")

THRESHOLD = 0.575
REJECTION = "Bu sorunun cevabı dokümanlarımda yer almamaktadır."


def _hit(cid, sim, text="gerçek chunk metni", title="Anemi Nedir?",
         source="atlas", url="https://example.com/a", parent="doc_00000"):
    return {
        "chunk_id": cid, "similarity": sim, "chunk_text": text, "title": title,
        "source": source, "url": url, "parent_id": parent,
    }


class FakeEmbedder:
    def encode_queries(self, questions):
        return [[0.0] * 4 for _ in questions]


class FakeStore:
    def __init__(self, hits):
        self._hits = hits

    def search(self, vector, top_k):
        return self._hits[:top_k]


# --- accepted (LLM available) --------------------------------------------- #

def test_accepted_rendering_with_llm():
    hits = [_hit("c1", 0.72, text="Anemi, kırmızı kan hücresi eksikliğidir.")]
    llm = FakeLLMClient(answer="Anemi bir kansızlık durumudur.")
    vm = app_logic.build_view_model(
        "Anemi nedir?", hits, THRESHOLD, REJECTION, 6000,
        llm=llm, llm_available=True,
    )
    assert vm["status"] == "accepted"
    assert vm["accepted"] is True
    assert vm["llm_called"] is True
    assert vm["answer"] == "Anemi bir kansızlık durumudur."
    assert llm.call_count == 1
    # kaynaklar gerçek chunk metnini içerir
    assert vm["sources"][0]["chunk_text"].startswith("Anemi, kırmızı kan")
    assert vm["sources"][0]["title"] == "Anemi Nedir?"


# --- rejected ------------------------------------------------------------- #

def test_rejected_rendering_no_llm():
    hits = [_hit("c9", 0.42)]
    llm = FakeLLMClient()
    vm = app_logic.build_view_model(
        "Kleptomani nedir?", hits, THRESHOLD, REJECTION, 6000,
        llm=llm, llm_available=True,
    )
    assert vm["status"] == "rejected"
    assert vm["accepted"] is False
    assert vm["llm_called"] is False
    assert vm["answer"] == REJECTION
    assert vm["sources"] == []
    assert llm.call_count == 0  # eşik altı -> LLM hiç çağrılmaz


# --- retrieval-only (no API key) ------------------------------------------ #

def test_retrieval_only_when_no_api_key():
    hits = [_hit("c1", 0.80, text="Gerçek dataset chunk metni.")]
    llm = FakeLLMClient()
    vm = app_logic.build_view_model(
        "Anemi nedir?", hits, THRESHOLD, REJECTION, 6000,
        llm=llm, llm_available=False,   # API key yok
    )
    assert vm["status"] == "retrieval_only"
    assert vm["accepted"] is True          # eşik geçildi
    assert vm["llm_called"] is False       # ama LLM çağrılmadı
    assert vm["answer"] is None
    assert llm.call_count == 0
    # gerçek retrieval içeriği hâlâ görünür
    assert vm["sources"][0]["chunk_text"] == "Gerçek dataset chunk metni."
    assert "context_preview" in vm


# --- top-k retrieval -> UI modeli ----------------------------------------- #

def test_top_k_mapped_to_ui_model():
    hits = [_hit(f"c{i}", 0.9 - i * 0.05, text=f"metin {i}") for i in range(5)]
    vm = app_logic.build_view_model(
        "soru?", hits, THRESHOLD, REJECTION, 6000, llm=None, llm_available=False,
    )
    assert len(vm["top_chunks"]) == 5
    assert [c["rank"] for c in vm["top_chunks"]] == [1, 2, 3, 4, 5]
    assert vm["top_chunks"][0]["chunk_id"] == "c0"
    assert vm["retrieved_chunk_ids"] == ["c0", "c1", "c2", "c3", "c4"]
    # her top chunk gerekli alanları taşır
    for c in vm["top_chunks"]:
        assert set(c) >= {"rank", "similarity", "chunk_id", "title", "source",
                          "chunk_text", "url"}


def test_retrieve_uses_embedder_and_store():
    hits = [_hit("c1", 0.7), _hit("c2", 0.6), _hit("c3", 0.5)]
    out = app_logic.retrieve(FakeEmbedder(), FakeStore(hits), top_k=2, question="q")
    assert [h["chunk_id"] for h in out] == ["c1", "c2"]  # top_k=2 uygulanır


def test_empty_retrieval_is_rejected():
    vm = app_logic.build_view_model(
        "soru?", [], THRESHOLD, REJECTION, 6000, llm=None, llm_available=False,
    )
    assert vm["status"] == "rejected"
    assert vm["top_similarity"] == 0.0
    assert vm["top_chunks"] == []


# --- örnek soru butonları ------------------------------------------------- #

def test_example_questions_constant():
    examples = app_logic.EXAMPLE_QUESTIONS
    assert len(examples) == 3
    questions = [q for _icon, q in examples]
    assert questions == [
        "Anemi nedir ve belirtileri nelerdir?",
        "Kalp yetmezliği belirtileri nelerdir?",
        "Uyku apnesi nedir?",
    ]
    # her örnekte bir ikon (emoji) ve boş olmayan soru bulunur
    for icon, q in examples:
        assert icon and q.strip()


def test_apply_example_sets_input_state():
    state = {}
    app_logic.apply_example(state, "Anemi nedir ve belirtileri nelerdir?")
    assert state[app_logic.QUESTION_KEY] == "Anemi nedir ve belirtileri nelerdir?"
    # ikinci bir örnek üzerine yazar
    app_logic.apply_example(state, "Uyku apnesi nedir?")
    assert state[app_logic.QUESTION_KEY] == "Uyku apnesi nedir?"
