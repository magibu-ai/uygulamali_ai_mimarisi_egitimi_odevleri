"""
retriever.py — Threshold bazlı retrieval mantığı.

Kullanıcı sorusunu vektörleştirir, ChromaDB'den en yakın chunk'ları çeker,
benzerlik eşiğini kontrol eder. Eşik altındaysa LLM'e gitmeden reddeder.
"""

import logging
from typing import Dict, Any, List, Optional

from src.embedding import get_embedding_model
from src.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Varsayılan threshold (benchmark ile kalibre edilecek)
DEFAULT_THRESHOLD = 0.55
DEFAULT_TOP_K = 5

# Eşik altında dönecek ret mesajı
REJECTION_MESSAGE = "Bu sorunun cevabı dokümanlarımda yer almamaktadır."


class Retriever:
    """Threshold bazlı retrieval sistemi."""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        threshold: float = DEFAULT_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
    ):
        """
        Retriever'ı başlatır.

        Args:
            vector_store: VectorStore instance. None ise yeni oluşturulur.
            threshold: Benzerlik eşiği (0-1 arası). Altındaki sonuçlar reddedilir.
            top_k: Döndürülecek maksimum chunk sayısı.
        """
        self.embedding_model = get_embedding_model()
        self.vector_store = vector_store or VectorStore()
        self.threshold = threshold
        self.top_k = top_k

        logger.info(
            f"Retriever başlatıldı (threshold={self.threshold}, top_k={self.top_k})"
        )

    def retrieve(
        self,
        query: str,
        threshold: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Sorguyu vektörleştirir ve threshold kontrolüyle sonuçları döndürür.

        Args:
            query: Kullanıcı sorusu.
            threshold: Benzerlik eşiği (None ise varsayılan kullanılır).
            top_k: Döndürülecek chunk sayısı (None ise varsayılan kullanılır).

        Returns:
            Dict:
                - status: "found" veya "rejected"
                - message: Ret mesajı (sadece rejected durumunda)
                - chunks: Bulunan chunk listesi (sadece found durumunda)
                - scores: Benzerlik skorları
                - top_score: En yüksek benzerlik skoru
                - query: Orijinal sorgu
        """
        if threshold is None:
            threshold = self.threshold
        if top_k is None:
            top_k = self.top_k

        # Sorguyu vektörleştir
        query_embedding = self.embedding_model.encode_query(query)

        # ChromaDB'den top-k sonuçları al
        results = self.vector_store.query_with_scores(query_embedding, k=top_k)

        if not results:
            logger.info(f"Sorgu için sonuç bulunamadı: '{query[:50]}...'")
            return {
                "status": "rejected",
                "message": REJECTION_MESSAGE,
                "chunks": [],
                "scores": [],
                "top_score": 0.0,
                "query": query,
            }

        # En yüksek benzerlik skoru
        top_score = results[0]["similarity_score"]
        scores = [r["similarity_score"] for r in results]

        logger.info(
            f"Sorgu: '{query[:50]}...' → top_score={top_score:.4f}, "
            f"threshold={threshold}"
        )

        # Threshold kontrolü
        if top_score < threshold:
            logger.info(
                f"Eşik altında ({top_score:.4f} < {threshold}). Sorgu reddedildi."
            )
            return {
                "status": "rejected",
                "message": REJECTION_MESSAGE,
                "chunks": [],
                "scores": scores,
                "top_score": top_score,
                "query": query,
            }

        # Eşik üzerindeki chunk'ları filtrele
        filtered_chunks = []
        filtered_scores = []
        for result in results:
            if result["similarity_score"] >= threshold:
                filtered_chunks.append({
                    "text": result["text"],
                    "metadata": result["metadata"],
                    "score": result["similarity_score"],
                })
                filtered_scores.append(result["similarity_score"])

        logger.info(
            f"Eşik üzerinde {len(filtered_chunks)} chunk bulundu."
        )

        return {
            "status": "found",
            "chunks": filtered_chunks,
            "scores": filtered_scores,
            "top_score": top_score,
            "query": query,
        }

    def retrieve_raw(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Threshold kontrolü olmadan ham retrieval sonuçlarını döndürür.
        Threshold analizi ve benchmark için kullanılır.

        Args:
            query: Kullanıcı sorusu.
            top_k: Döndürülecek chunk sayısı.

        Returns:
            List[Dict]: Her sonuç için {text, metadata, similarity_score} listesi.
        """
        query_embedding = self.embedding_model.encode_query(query)
        return self.vector_store.query_with_scores(query_embedding, k=top_k)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("Retriever Modülü — Test")
    print("=" * 60)

    retriever = Retriever()

    test_queries = [
        "Diyabet hastalığının belirtileri nelerdir?",
        "Mars gezegeninde yaşam var mı?",
    ]

    for query in test_queries:
        print(f"\n{'='*40}")
        print(f"Sorgu: {query}")
        result = retriever.retrieve(query)
        print(f"Durum: {result['status']}")
        print(f"En yüksek skor: {result['top_score']:.4f}")

        if result["status"] == "found":
            for i, chunk in enumerate(result["chunks"]):
                print(f"\n  Chunk {i+1} (skor: {chunk['score']:.4f}):")
                print(f"  Başlık: {chunk['metadata'].get('title', 'N/A')}")
                print(f"  Metin: {chunk['text'][:100]}...")
        else:
            print(f"Mesaj: {result['message']}")
