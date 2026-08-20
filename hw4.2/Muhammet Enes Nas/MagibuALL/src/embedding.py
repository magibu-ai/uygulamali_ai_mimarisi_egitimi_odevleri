"""
embedding.py — magibu/embeddingmagibu-200m embedding modeli wrapper.

Model: magibu/embeddingmagibu-200m
- 768 boyutlu, ℓ₂-normalize edilmiş vektörler
- 8192 token context window
- Türkçe odaklı, 40+ dil desteği
- Gemma3 tabanlı backbone, mean pooling
"""

import logging
from typing import List, Union

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "magibu/embeddingmagibu-200m"
EMBEDDING_DIM = 768
BATCH_SIZE = 64


class EmbeddingModel:
    """magibu/embeddingmagibu-200m embedding modeli sarmalayıcısı."""

    def __init__(self, model_name=MODEL_NAME, device=None):
        """
        Embedding modelini yükler.

        Args:
            model_name: Hugging Face model adı.
            device: Torch device (None ise otomatik seçilir).
        """
        logger.info(f"Embedding modeli yükleniyor: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        self.model_name = model_name
        self.embedding_dim = EMBEDDING_DIM
        logger.info(
            f"Model yüklendi. Boyut: {self.embedding_dim}, "
            f"Max seq length: {self.model.max_seq_length}, "
            f"Device: {self.model.device}"
        )

    def encode_texts(
        self,
        texts: List[str],
        batch_size: int = BATCH_SIZE,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Metin listesini vektörlere dönüştürür.

        Args:
            texts: Embedding oluşturulacak metin listesi.
            batch_size: Batch boyutu.
            show_progress: Progress bar gösterilsin mi.

        Returns:
            np.ndarray: (N, 768) boyutlu normalize edilmiş vektörler.
        """
        logger.info(f"{len(texts)} metin vektörleştiriliyor (batch_size={batch_size})")

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
        )

        logger.info(f"Embedding tamamlandı. Shape: {embeddings.shape}")
        return embeddings

    def encode_query(self, query: str) -> np.ndarray:
        """
        Tek bir sorguyu vektöre dönüştürür.

        Args:
            query: Sorgu metni.

        Returns:
            np.ndarray: (768,) boyutlu normalize edilmiş vektör.
        """
        embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding[0]

    def encode_chunks(
        self,
        chunks: List[dict],
        batch_size: int = BATCH_SIZE,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Chunk listesini vektörlere dönüştürür.

        Args:
            chunks: Chunk dict listesi (her birinde "text" anahtarı olmalı).
            batch_size: Batch boyutu.
            show_progress: Progress bar gösterilsin mi.

        Returns:
            np.ndarray: (N, 768) boyutlu normalize edilmiş vektörler.
        """
        texts = [chunk["text"] for chunk in chunks]
        return self.encode_texts(texts, batch_size, show_progress)


# Singleton pattern — modeli birden fazla yüklememek için
_model_instance = None


def get_embedding_model(model_name=MODEL_NAME, device=None):
    """
    Embedding modeli singleton instance'ını döndürür.

    Args:
        model_name: Hugging Face model adı.
        device: Torch device.

    Returns:
        EmbeddingModel instance.
    """
    global _model_instance
    if _model_instance is None:
        _model_instance = EmbeddingModel(model_name, device)
    return _model_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("Embedding Modülü — Test")
    print("=" * 60)

    model = get_embedding_model()

    # Test sorguları
    test_texts = [
        "Diyabet hastalığının belirtileri nelerdir?",
        "Tip 2 diyabet tedavisi nasıl yapılır?",
        "Ankara'nın başkent oluş tarihi nedir?",  # alakasız soru
    ]

    embeddings = model.encode_texts(test_texts, show_progress=False)

    print(f"\nModel: {model.model_name}")
    print(f"Embedding boyutu: {model.embedding_dim}")
    print(f"Test metin sayısı: {len(test_texts)}")
    print(f"Embedding shape: {embeddings.shape}")

    # Benzerlik matrisi (normalize vektörlerde dot product = cosine similarity)
    similarity_matrix = np.dot(embeddings, embeddings.T)
    print(f"\nBenzerlik matrisi:")
    for i, text in enumerate(test_texts):
        print(f"  [{i}] {text[:50]}...")
    print(f"\n{similarity_matrix.round(4)}")
