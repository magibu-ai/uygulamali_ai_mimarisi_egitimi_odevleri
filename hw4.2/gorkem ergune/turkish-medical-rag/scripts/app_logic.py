"""Streamlit'ten bağımsız, test edilebilir UI mantığı.

Üretim bileşenlerini (Embedder, ChromaStore, config eşiği ve `src.rag.prompt`
yardımcıları) yeniden kullanır; hiçbir production kodunu değiştirmez. Streamlit
import etmez, böylece tamamen offline test edilebilir.

Retrieval-only desteği: LLM yalnızca `llm_available` True olduğunda çağrılır.
API key yoksa (llm_available False) gerçek retrieval sonucu döner ama Claude
çağrılmaz.
"""
from __future__ import annotations

from typing import Any

from src.rag.prompt import build_context, build_prompt

# Streamlit session-state anahtarı (soru input alanı) ve örnek sorular.
# Örnek sorular corpus içeriğiyle uyumludur (Anemi / Kalp Yetmezliği / Uyku
# Apnesi hepsi seçili 300 dokümanda mevcuttur), böylece gerçek retrieval çıkar.
QUESTION_KEY = "question_input"

EXAMPLE_QUESTIONS = [
    ("🩸", "Anemi nedir ve belirtileri nelerdir?"),
    ("❤️", "Kalp yetmezliği belirtileri nelerdir?"),
    ("🫁", "Uyku apnesi nedir?"),
]


def apply_example(state: Any, question: str) -> None:
    """Örnek soruya tıklanınca input alanını doldurur (Streamlit on_click callback).

    `state` sözlük-benzeri (Streamlit session_state veya dict) olabilir, bu yüzden
    streamlit olmadan da test edilebilir.
    """
    state[QUESTION_KEY] = question


def chunk_to_view(hit: dict[str, Any], rank: int) -> dict[str, Any]:
    """Bir retrieval sonucunu UI için tam alanlı bir sözlüğe çevirir."""
    return {
        "rank": rank,
        "similarity": round(float(hit.get("similarity", 0.0)), 4),
        "chunk_id": hit.get("chunk_id", ""),
        "parent_id": hit.get("parent_id", ""),
        "title": hit.get("title", ""),
        "source": hit.get("source", ""),
        "url": hit.get("url", ""),
        "chunk_text": hit.get("chunk_text", ""),
    }


def retrieve(embedder: Any, store: Any, top_k: int, question: str) -> list[dict[str, Any]]:
    """Üretim retrieval yolu: E5 sorgu embedding -> ChromaDB top-k."""
    vector = embedder.encode_queries([question])[0]
    return store.search(vector, top_k=top_k)


def build_view_model(
    question: str,
    hits: list[dict[str, Any]],
    threshold: float,
    rejection_message: str,
    max_context_chars: int,
    llm: Any = None,
    llm_available: bool = False,
) -> dict[str, Any]:
    """Retrieval sonuçları + eşik kapısından UI görünüm modeli üretir.

    status alanları:
      * "rejected"        -> top-1 < eşik; LLM çağrılmaz.
      * "accepted"        -> top-1 >= eşik ve LLM mevcut; Claude cevabı üretilir.
      * "retrieval_only"  -> top-1 >= eşik ama API key yok; sadece retrieval.
    """
    top1 = float(hits[0]["similarity"]) if hits else 0.0
    accepted = bool(hits) and top1 >= threshold
    top_chunks = [chunk_to_view(h, i + 1) for i, h in enumerate(hits)]

    view: dict[str, Any] = {
        "question": question,
        "top_similarity": round(top1, 4),
        "threshold": threshold,
        "accepted": accepted,
        "top_chunks": top_chunks,
        "retrieved_chunk_ids": [h.get("chunk_id", "") for h in hits],
    }

    if not accepted:
        view.update({
            "status": "rejected",
            "answer": rejection_message,
            "llm_called": False,
            "sources": [],
        })
        return view

    # Kabul edildi: bağlam ve kaynaklar retrieval'dan (gerçek chunk metniyle) kurulur.
    context_text, used = build_context(hits, max_context_chars)
    sources = [chunk_to_view(h, i + 1) for i, h in enumerate(used)]

    if llm_available and llm is not None:
        system, user = build_prompt(question, context_text)
        answer = llm.generate(system, user)
        view.update({
            "status": "accepted",
            "answer": answer,
            "llm_called": True,
            "sources": sources,
        })
    else:
        view.update({
            "status": "retrieval_only",
            "answer": None,
            "llm_called": False,
            "sources": sources,
            "context_preview": context_text,
        })
    return view
