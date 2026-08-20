"""
rag_pipeline.py — Uçtan uca RAG pipeline.

Soru → Retriever (threshold kontrolü) → LLM (cevap üretimi) → Sonuç

Tüm adımları loglar ve sonuç dict'i döndürür.
"""

import logging
import time
from typing import Dict, Any, Optional

from src.retriever import Retriever, REJECTION_MESSAGE
from src.llm import generate_answer

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Uçtan uca RAG (Retrieval-Augmented Generation) pipeline."""

    def __init__(
        self,
        threshold: float = 0.55,
        top_k: int = 5,
        colab_url: Optional[str] = None,
    ):
        """
        RAG pipeline'ı başlatır.

        Args:
            threshold: Benzerlik eşiği.
            top_k: Retrieval'da döndürülecek chunk sayısı.
            colab_url: Colab LLM endpoint URL'i.
        """
        self.retriever = Retriever(threshold=threshold, top_k=top_k)
        self.colab_url = colab_url
        self.threshold = threshold
        self.top_k = top_k

        logger.info(
            f"RAG Pipeline başlatıldı (threshold={threshold}, top_k={top_k})"
        )

    def ask(self, question: str) -> Dict[str, Any]:
        """
        Kullanıcı sorusunu alır, RAG pipeline'ından geçirir ve cevap döndürür.

        Args:
            question: Kullanıcı sorusu.

        Returns:
            Dict:
                - question: Orijinal soru
                - answer: Üretilen cevap veya ret mesajı
                - status: "found" veya "rejected"
                - top_score: En yüksek benzerlik skoru
                - scores: Tüm benzerlik skorları
                - chunks: Bulunan chunk'lar (found durumunda)
                - source: Cevap kaynağı ("colab_gemma", "fallback_context_only", "threshold_rejection")
                - elapsed_seconds: İşlem süresi
        """
        start_time = time.time()

        logger.info(f"\n{'='*50}")
        logger.info(f"Soru: {question}")
        logger.info(f"{'='*50}")

        # 1. Retrieval + Threshold kontrolü
        retrieval_result = self.retriever.retrieve(question)

        if retrieval_result["status"] == "rejected":
            elapsed = time.time() - start_time
            logger.info(
                f"Sorgu reddedildi (top_score={retrieval_result['top_score']:.4f}). "
                f"Süre: {elapsed:.2f}s"
            )
            return {
                "question": question,
                "answer": REJECTION_MESSAGE,
                "status": "rejected",
                "top_score": retrieval_result["top_score"],
                "scores": retrieval_result["scores"],
                "chunks": [],
                "source": "threshold_rejection",
                "elapsed_seconds": elapsed,
            }

        # 2. LLM ile cevap üretimi
        chunks = retrieval_result["chunks"]
        llm_result = generate_answer(
            chunks=chunks,
            question=question,
            colab_url=self.colab_url,
        )

        elapsed = time.time() - start_time
        logger.info(
            f"Cevap üretildi (kaynak: {llm_result['source']}). "
            f"Süre: {elapsed:.2f}s"
        )

        return {
            "question": question,
            "answer": llm_result["answer"],
            "status": "found",
            "top_score": retrieval_result["top_score"],
            "scores": retrieval_result["scores"],
            "chunks": chunks,
            "source": llm_result["source"],
            "elapsed_seconds": elapsed,
        }


def interactive_mode(pipeline: RAGPipeline):
    """
    Etkileşimli soru-cevap modu.
    """
    print("\n" + "=" * 60)
    print("🏥 Türkçe Tıbbi RAG Sistemi — Etkileşimli Mod")
    print("=" * 60)
    print("Çıkmak için 'q' veya 'quit' yazın.\n")

    while True:
        try:
            question = input("📝 Sorunuz: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGörüşmek üzere! 👋")
            break

        if not question:
            continue
        if question.lower() in ("q", "quit", "exit", "çık"):
            print("\nGörüşmek üzere! 👋")
            break

        result = pipeline.ask(question)

        print(f"\n{'─'*40}")
        print(f"📊 Durum: {result['status']}")
        print(f"📈 En yüksek skor: {result['top_score']:.4f}")
        print(f"⏱️  Süre: {result['elapsed_seconds']:.2f}s")
        print(f"📡 Kaynak: {result['source']}")
        print(f"\n💬 Cevap:\n{result['answer']}")

        if result["chunks"]:
            print(f"\n📚 Kullanılan kaynaklar:")
            for i, chunk in enumerate(result["chunks"], 1):
                title = chunk.get("metadata", {}).get("title", "N/A")
                score = chunk.get("score", 0.0)
                print(f"  {i}. {title} (skor: {score:.4f})")

        print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    pipeline = RAGPipeline()
    interactive_mode(pipeline)
