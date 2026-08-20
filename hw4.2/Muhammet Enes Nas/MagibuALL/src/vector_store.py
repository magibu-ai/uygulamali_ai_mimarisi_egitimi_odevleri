"""
vector_store.py — ChromaDB vektör veritabanı yönetimi.

ChromaDB PersistentClient ile local dosya tabanlı vektör depolama.
Koleksiyon: turkish_medical_articles
Mesafe metriği: cosine
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
import numpy as np

logger = logging.getLogger(__name__)

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_DB_DIR = PROJECT_ROOT / "data" / "chroma_db"

COLLECTION_NAME = "turkish_medical_articles"
BATCH_SIZE = 5000  # ChromaDB upsert batch limiti


class VectorStore:
    """ChromaDB tabanlı vektör veritabanı yöneticisi."""

    def __init__(self, persist_dir=None, collection_name=COLLECTION_NAME):
        """
        ChromaDB client ve koleksiyonu başlatır.

        Args:
            persist_dir: Veritabanı dizini. None ise varsayılan kullanılır.
            collection_name: Koleksiyon adı.
        """
        if persist_dir is None:
            persist_dir = CHROMA_DB_DIR

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ChromaDB başlatılıyor: {self.persist_dir}")
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"Koleksiyon hazır: '{collection_name}' "
            f"(mevcut eleman sayısı: {self.collection.count()})"
        )

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: np.ndarray,
    ):
        """
        Chunk'ları ve embedding'leri ChromaDB'ye yükler.

        Args:
            chunks: Chunk dict listesi (chunk_id, text, metadata).
            embeddings: (N, 768) boyutlu numpy array.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunk sayısı ({len(chunks)}) ile embedding sayısı "
                f"({len(embeddings)}) eşleşmiyor."
            )

        total = len(chunks)
        logger.info(f"{total} chunk ChromaDB'ye yükleniyor...")

        # Batch'ler halinde upsert
        for start in range(0, total, BATCH_SIZE):
            end = min(start + BATCH_SIZE, total)
            batch_chunks = chunks[start:end]
            batch_embeddings = embeddings[start:end]

            ids = [c["chunk_id"] for c in batch_chunks]
            documents = [c["text"] for c in batch_chunks]
            metadatas = [c["metadata"] for c in batch_chunks]
            embedding_list = batch_embeddings.tolist()

            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embedding_list,
                metadatas=metadatas,
            )

            logger.info(
                f"  Batch upsert: {start+1}-{end}/{total}"
            )

        logger.info(
            f"Upsert tamamlandı. Koleksiyon eleman sayısı: {self.collection.count()}"
        )

    def query(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        where: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Verilen embedding'e en yakın k chunk'ı döndürür.

        Args:
            query_embedding: (768,) boyutlu sorgu vektörü.
            k: Döndürülecek sonuç sayısı.
            where: Metadata filtresi (opsiyonel).

        Returns:
            Dict: ChromaDB query sonucu (ids, documents, metadatas, distances).
                  distances cosine distance'tır (0 = aynı, 2 = tam zıt).
                  Benzerlik skoru = 1 - distance.
        """
        query_params = {
            "query_embeddings": [query_embedding.tolist()],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }

        if where:
            query_params["where"] = where

        results = self.collection.query(**query_params)
        return results

    def query_with_scores(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Sorgu sonuçlarını benzerlik skorlarıyla birlikte döndürür.

        Args:
            query_embedding: (768,) boyutlu sorgu vektörü.
            k: Döndürülecek sonuç sayısı.

        Returns:
            List[Dict]: Her sonuç için {text, metadata, similarity_score} dict listesi.
                        similarity_score: 0-1 arası (1 = tam benzer).
        """
        raw_results = self.query(query_embedding, k)

        results = []
        if raw_results["ids"] and raw_results["ids"][0]:
            for i in range(len(raw_results["ids"][0])):
                # ChromaDB cosine distance → benzerlik skoru
                distance = raw_results["distances"][0][i]
                similarity = 1.0 - distance

                results.append({
                    "chunk_id": raw_results["ids"][0][i],
                    "text": raw_results["documents"][0][i],
                    "metadata": raw_results["metadatas"][0][i],
                    "similarity_score": similarity,
                })

        return results

    def get_all_data(self):
        """
        Koleksiyondaki tüm verileri döndürür (export için).

        Returns:
            Dict: Tüm ids, documents, metadatas, embeddings.
        """
        count = self.collection.count()
        if count == 0:
            return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

        return self.collection.get(
            include=["documents", "metadatas", "embeddings"],
        )

    def get_stats(self) -> Dict[str, Any]:
        """Koleksiyon istatistiklerini döndürür."""
        count = self.collection.count()
        return {
            "collection_name": self.collection.name,
            "total_chunks": count,
            "persist_dir": str(self.persist_dir),
        }

    def delete_collection(self):
        """Koleksiyonu siler (dikkatli kullanın)."""
        self.client.delete_collection(self.collection.name)
        logger.warning(f"Koleksiyon silindi: {self.collection.name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("Vector Store Modülü — Test")
    print("=" * 60)

    store = VectorStore()
    stats = store.get_stats()
    print(f"\nKoleksiyon: {stats['collection_name']}")
    print(f"Eleman sayısı: {stats['total_chunks']}")
    print(f"Dizin: {stats['persist_dir']}")
