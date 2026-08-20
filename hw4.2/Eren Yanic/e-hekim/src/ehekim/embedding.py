"""Embedding backend for magibu/embeddingmagibu-200m.

The model is *asymmetric*: it was distilled with distinct instruction prefixes
for queries and for documents. Encoding a query with the document prefix (or
vice versa) silently degrades cosine similarity, which would in turn corrupt the
threshold calibration. To make that mistake impossible, every call site in this
project goes through :class:`Embedder` and never touches SentenceTransformer
directly.

The document prefix is built per item so the article title can be carried into
the vector (``title: <title> | text: <chunk>``) — the format the model was
trained on. SentenceTransformer applies one prompt per ``encode`` call, so the
prefix is materialised into the string instead of using ``prompt_name``; the
result is byte-identical, and ``tests/test_embedding.py`` asserts that.

Output vectors are L2-normalised by the model's final ``Normalize`` module, so
dot product equals cosine similarity and Chroma's cosine distance is exactly
``1 - similarity``.
"""

from __future__ import annotations

import logging
import threading
from typing import Iterable, Sequence

import numpy as np

from .config import (
    DOCUMENT_PROMPT_TEMPLATE,
    DOCUMENT_TITLE_FALLBACK,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_ID,
    QUERY_PROMPT,
)

logger = logging.getLogger(__name__)


def build_document_input(chunk_text: str, title: str | None) -> str:
    """Render the exact string the model should see for a document chunk."""
    clean_title = (title or "").strip() or DOCUMENT_TITLE_FALLBACK
    # Keep the delimiter unambiguous: a title containing '|' must not be able to
    # forge a second field.
    clean_title = clean_title.replace("|", "/")
    return DOCUMENT_PROMPT_TEMPLATE.format(title=clean_title) + chunk_text


def build_query_input(query: str) -> str:
    """Render the exact string the model should see for a search query."""
    return QUERY_PROMPT + query.strip()


def resolve_device(requested: str | None = None) -> str:
    import torch

    if requested:
        return requested
    return "cuda" if torch.cuda.is_available() else "cpu"


class Embedder:
    """Thread-safe wrapper around the SentenceTransformer model."""

    def __init__(
        self,
        model_id: str = EMBEDDING_MODEL_ID,
        device: str | None = None,
        batch_size: int = 32,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_id = model_id
        self.device = resolve_device(device)
        self.batch_size = batch_size
        logger.info("Loading embedding model %s on %s", model_id, self.device)
        self.model = SentenceTransformer(model_id, device=self.device)
        self.model.eval()
        # Guards the underlying model during concurrent requests: a single
        # SentenceTransformer instance is not safe for parallel forward passes.
        self._lock = threading.Lock()

        # sentence-transformers 5.3 renamed this accessor; support both.
        get_dim = getattr(self.model, "get_embedding_dimension", None) or (
            self.model.get_sentence_embedding_dimension
        )
        dim = get_dim()
        if dim != EMBEDDING_DIM:
            raise RuntimeError(
                f"Beklenen embedding boyutu {EMBEDDING_DIM}, model {dim} döndürdü."
            )

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    @property
    def tokenizer(self):
        """The model's own tokenizer, so chunk sizes are measured in the units
        the model actually consumes rather than in an approximation."""
        return self.model.tokenizer

    def _encode(self, texts: Sequence[str], show_progress: bool = False) -> np.ndarray:
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        with self._lock:
            vectors = self.model.encode(
                list(texts),
                batch_size=self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=show_progress,
            )
        return np.asarray(vectors, dtype=np.float32)

    def encode_documents(
        self,
        chunks: Sequence[str],
        titles: Sequence[str | None] | None = None,
        show_progress: bool = False,
    ) -> np.ndarray:
        if titles is None:
            titles = [None] * len(chunks)
        if len(titles) != len(chunks):
            raise ValueError("titles ve chunks aynı uzunlukta olmalı.")
        prepared = [build_document_input(c, t) for c, t in zip(chunks, titles)]
        return self._encode(prepared, show_progress=show_progress)

    def encode_queries(self, queries: Iterable[str], show_progress: bool = False) -> np.ndarray:
        prepared = [build_query_input(q) for q in queries]
        return self._encode(prepared, show_progress=show_progress)

    def encode_query(self, query: str) -> np.ndarray:
        return self.encode_queries([query])[0]


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder(device: str | None = None, batch_size: int = 32) -> Embedder:
    """Process-wide singleton; the model is ~200M params and loads once."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = Embedder(device=device, batch_size=batch_size)
    return _embedder
