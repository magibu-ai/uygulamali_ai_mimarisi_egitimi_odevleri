"""Basit CLI demo — terminalden Türkçe tıbbi soru sorup RAGPipeline'dan cevap alır.

Bu yalnızca bir demo/CLI katmanıdır. Mevcut retrieval / embedding / threshold /
RAG davranışını DEĞİŞTİRMEZ; sadece `src.rag.pipeline.build_pipeline` ile üretim
bileşenlerini (E5 embedder + mevcut ChromaDB + AnthropicLLMClient) bağlar.

Kullanım:
    python scripts/chat.py --question "Anemi nedir?"   # tek soru
    python scripts/chat.py                             # interaktif mod (Ctrl+C ile çıkış)

Notlar:
- Varsayılan olarak mevcut artifacts/chroma kullanılır; dataset/chunk/embedding
  pipeline'ı yeniden çalıştırılmaz.
- API anahtarı config'te belirtilen ANTHROPIC_API_KEY ortam değişkeninden okunur
  (AnthropicLLMClient içinde) ve HİÇBİR ZAMAN ekrana yazılmaz veya kaydedilmez.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402
from src.rag.pipeline import build_pipeline  # noqa: E402


def format_result(result: dict[str, Any]) -> str:
    """RAGPipeline sonucunu okunabilir metne çevirir (saf fonksiyon, test edilebilir)."""
    lines: list[str] = []
    lines.append(f"Soru       : {result['question']}")
    lines.append(
        f"Benzerlik  : {result['top_similarity']:.4f}  "
        f"(eşik = {result['threshold']})"
    )

    if result["accepted"]:
        lines.append("Durum      : KABUL EDİLDİ"
                     + ("  (LLM çağrıldı)" if result.get("llm_called") else ""))
        lines.append("")
        lines.append("Cevap:")
        lines.append(result["answer"])
        sources = result.get("sources") or []
        if sources:
            lines.append("")
            lines.append("Kaynaklar:")
            for i, s in enumerate(sources, start=1):
                lines.append(
                    f"  [{i}] {s.get('title', '')}  "
                    f"(benzerlik {s.get('similarity', 0.0):.4f}, "
                    f"kaynak: {s.get('source', '')})"
                )
                lines.append(f"      URL: {s.get('url', '')}")
                lines.append(f"      chunk_id: {s.get('chunk_id', '')}")
    else:
        lines.append("Durum      : REDDEDİLDİ  (LLM çağrılmadı)")
        lines.append("")
        lines.append(result["answer"])  # tam reddetme mesajı

    return "\n".join(lines)


def run_once(pipeline: Any, question: str, out: Callable[[str], None] = print) -> None:
    """Tek bir soruyu çalıştırır ve sonucu yazdırır."""
    out(format_result(pipeline.answer(question)))


def interactive(
    pipeline: Any,
    in_: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
) -> None:
    """İnteraktif döngü. Ctrl+C / EOF veya 'çık' ile düzgün şekilde çıkar."""
    out("Türkçe tıbbi soru-cevap demosu. Çıkmak için Ctrl+C.")
    while True:
        try:
            question = in_("\nSoru> ").strip()
        except (EOFError, KeyboardInterrupt):
            out("\nÇıkılıyor...")
            break
        if not question:
            continue
        if question.lower() in {"çık", "cik", "exit", "quit"}:
            out("Çıkılıyor...")
            break
        try:
            run_once(pipeline, question, out=out)
        except KeyboardInterrupt:
            out("\nÇıkılıyor...")
            break


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Türkçe tıbbi RAG demo (mevcut ChromaDB üzerinden)."
    )
    parser.add_argument(
        "--question", "-q", default=None,
        help="Tek soru çalıştır. Verilmezse interaktif mod açılır.",
    )
    args = parser.parse_args(argv)

    config = load_config()
    # Mevcut ChromaDB'ye bağlanır; embedder + LLM config'ten kurulur.
    pipeline = build_pipeline(config)

    if args.question:
        run_once(pipeline, args.question)
    else:
        interactive(pipeline)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nÇıkılıyor...")
