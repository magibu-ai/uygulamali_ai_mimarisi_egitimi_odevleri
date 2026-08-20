"""Sorgu embedding'i — corpus ile aynı model, e5 konvansiyonuyla."""

import os
import threading

from sentence_transformers import SentenceTransformer

_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_query(text: str):
    """e5 konvansiyonu: sorgular 'query: ' prefix'i ile embed edilir."""
    vector = _get_model().encode(f"query: {text}", normalize_embeddings=True)
    return vector.tolist()
