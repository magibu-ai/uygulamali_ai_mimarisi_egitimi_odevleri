"""Deterministic context, prompt, and source construction for the RAG layer.

Pure functions (no model, no DB), so they are fully unit-testable. The threshold
decision is NOT represented here — it is an application-level gate in the
pipeline, never part of the LLM prompt.
"""
from __future__ import annotations

from typing import Any

# System instructions: strict grounding, Turkish, concise. Kept as a constant
# (it is prompt text, not a per-deployment config value).
SYSTEM_INSTRUCTIONS = (
    "Sen Türkçe tıbbi bir soru-cevap asistanısın. Aşağıdaki kurallara KESİNLİKLE "
    "uy:\n"
    "1. Yalnızca sana verilen RETRIEVED CONTEXT (bağlam) içindeki bilgilere "
    "dayanarak cevap ver.\n"
    "2. Dış bilgi veya genel kültür KULLANMA. Bağlamda olmayan hiçbir tıbbi "
    "bilgiyi uydurma.\n"
    "3. Eğer bağlam soruyu yanıtlamak için yeterli bilgi içermiyorsa, açıkça "
    "\"Sağlanan belgeler bu soruyu yanıtlamak için yeterli bilgi içermemektedir.\" "
    "de.\n"
    "4. Cevabın Türkçe, kısa ve doğrudan soruyu yanıtlayacak şekilde olsun.\n"
    "5. Tıbbi iddiaları yalnızca bağlamdaki metne dayandır."
)


def sort_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort retrieved chunks by descending similarity (tie-break by chunk_id)."""
    return sorted(
        chunks,
        key=lambda c: (-float(c.get("similarity", 0.0)), c.get("chunk_id", "")),
    )


def build_context(
    chunks: list[dict[str, Any]], max_chars: int
) -> tuple[str, list[dict[str, Any]]]:
    """Build the LLM context from retrieved chunks (deterministic).

    Chunks are sorted by descending similarity and included in order until the
    ``max_chars`` budget is reached. Returns ``(context_text, used_chunks)``.
    The first chunk is always included even if it alone exceeds the budget (so a
    non-empty accepted query never yields empty context).
    """
    ordered = sort_chunks(chunks)
    blocks: list[str] = []
    used: list[dict[str, Any]] = []
    total = 0
    for index, chunk in enumerate(ordered, start=1):
        block = (
            f"[Kaynak {index}] "
            f"Başlık: {chunk.get('title', '')} | "
            f"Kaynak: {chunk.get('source', '')} | "
            f"URL: {chunk.get('url', '')}\n"
            f"{chunk.get('chunk_text', '')}"
        )
        if used and total + len(block) > max_chars:
            break
        blocks.append(block)
        used.append(chunk)
        total += len(block)
    return "\n\n".join(blocks), used


def build_prompt(question: str, context_text: str) -> tuple[str, str]:
    """Build ``(system, user)`` with clearly separated sections."""
    user = (
        "USER QUESTION:\n"
        f"{question}\n\n"
        "RETRIEVED CONTEXT:\n"
        f"{context_text}"
    )
    return SYSTEM_INSTRUCTIONS, user


def build_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic source attribution from the chunks actually used.

    Only metadata returned by ChromaDB is exposed — never fabricated.
    """
    return [
        {
            "chunk_id": c.get("chunk_id", ""),
            "parent_id": c.get("parent_id", ""),
            "title": c.get("title", ""),
            "url": c.get("url", ""),
            "source": c.get("source", ""),
            "similarity": round(float(c.get("similarity", 0.0)), 4),
        }
        for c in chunks
    ]
