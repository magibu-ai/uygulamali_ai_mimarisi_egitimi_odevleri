"""Embedding generation (Phase 3).

Wraps the locked embedding model (``ytu-ce-cosmos/turkish-e5-large``) and
centralizes the e5-instruct encoding convention so that document and query
formatting can never diverge between evaluation and production retrieval:

  * document / chunk passages -> RAW text (no prefix)
  * queries                   -> "Instruct: {instruction}\nQuery: {question}"

The pure helpers (formatting, validation, normalization, context-length checks)
are model-free so they can be unit-tested without downloading the model. Only
the ``Embedder`` class touches ``sentence-transformers``.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np


# --------------------------------------------------------------------------- #
# Pure, model-free helpers (unit-testable without downloading the model)
# --------------------------------------------------------------------------- #

def format_query(question: str, instruction: str) -> str:
    """Format a query using the e5-instruct convention (single source of truth)."""
    return f"Instruct: {instruction}\nQuery: {question}"


def format_document(text: str) -> str:
    """Format a document/chunk passage: raw text, no prefix (e5-instruct)."""
    return text


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Return row-wise L2-normalized float32 vectors (zero rows left unchanged)."""
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (vectors / norms).astype(np.float32)


def find_overlength_chunks(
    chunk_ids: list[str],
    texts: list[str],
    count_tokens: Callable[[str], int],
    max_length: int,
) -> list[dict[str, int]]:
    """Return chunks whose tokenized length exceeds ``max_length``.

    ``count_tokens`` is injected so this can be tested with a stub tokenizer.
    """
    offenders: list[dict[str, int]] = []
    for chunk_id, text in zip(chunk_ids, texts):
        n = count_tokens(text)
        if n > max_length:
            offenders.append({"chunk_id": chunk_id, "tokens": n})
    return offenders


def assert_embeddings_valid(
    vectors: np.ndarray, expected_dim: int, norm_tol: float = 1e-3
) -> dict[str, float]:
    """Validate shape, dimension, finiteness, and normalization.

    Raises ``ValueError`` with a descriptive message on any failure. On success
    returns basic norm statistics.
    """
    if vectors.ndim != 2:
        raise ValueError(f"Embeddings must be 2-D, got shape {vectors.shape}.")
    if vectors.shape[1] != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dim}, "
            f"got {vectors.shape[1]}."
        )
    if np.isnan(vectors).any():
        raise ValueError("Embeddings contain NaN values.")
    if np.isinf(vectors).any():
        raise ValueError("Embeddings contain infinite values.")
    norms = np.linalg.norm(vectors, axis=1)
    max_dev = float(np.max(np.abs(norms - 1.0))) if len(norms) else 0.0
    if max_dev > norm_tol:
        raise ValueError(
            f"Embeddings are not L2-normalized (max deviation {max_dev:.6f} "
            f"exceeds tolerance {norm_tol})."
        )
    return {
        "norm_min": float(np.min(norms)) if len(norms) else 0.0,
        "norm_max": float(np.max(norms)) if len(norms) else 0.0,
        "norm_mean": float(np.mean(norms)) if len(norms) else 0.0,
        "norm_max_abs_deviation": max_dev,
    }


def check_alignment(chunk_ids: list[str], vectors: np.ndarray) -> None:
    """Ensure the number of ids matches the number of vectors."""
    if len(chunk_ids) != vectors.shape[0]:
        raise ValueError(
            f"Alignment error: {len(chunk_ids)} chunk ids vs "
            f"{vectors.shape[0]} vectors."
        )


# --------------------------------------------------------------------------- #
# Model-backed embedder
# --------------------------------------------------------------------------- #

class Embedder:
    """Loads the sentence-transformers model and produces embeddings."""

    def __init__(
        self,
        model_name: str,
        expected_dim: int,
        query_instruction: str,
        normalize: bool = True,
        batch_size: int = 32,
        device: str | None = None,
    ):
        self.model_name = model_name
        self.expected_dim = expected_dim
        self.query_instruction = query_instruction
        self.normalize = normalize
        self.batch_size = batch_size
        self.device = device
        self.model = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Embedder":
        emb = config["embedding"]
        return cls(
            model_name=emb["model_name"],
            expected_dim=emb["expected_dim"],
            query_instruction=emb["query_instruction"],
            normalize=emb["normalize"],
            batch_size=emb["batch_size"],
        )

    def load(self) -> "Embedder":
        from sentence_transformers import SentenceTransformer
        import torch

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(self.model_name, device=self.device)
        actual_dim = self.model.get_sentence_embedding_dimension()
        if actual_dim != self.expected_dim:
            raise ValueError(
                f"Model {self.model_name} reports dimension {actual_dim}, "
                f"expected {self.expected_dim}."
            )
        return self

    @property
    def max_seq_length(self) -> int:
        return int(self.model.max_seq_length)

    def count_tokens(self, text: str) -> int:
        """Token length under the MODEL's tokenizer, without truncation."""
        return len(
            self.model.tokenizer(
                text, add_special_tokens=True, truncation=False
            )["input_ids"]
        )

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32)

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode([format_document(t) for t in texts])

    def encode_queries(self, questions: list[str]) -> np.ndarray:
        return self._encode(
            [format_query(q, self.query_instruction) for q in questions]
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "embedding_dim": self.expected_dim,
            "normalize": self.normalize,
            "batch_size": self.batch_size,
            "device": self.device,
            "dtype": "float32",
            "max_seq_length": self.max_seq_length if self.model else None,
            "query_instruction": self.query_instruction,
        }


def get_model_revision(model_name: str) -> str | None:
    """Best-effort model commit hash from the Hub. Returns None if unavailable
    (never fabricated)."""
    try:
        from huggingface_hub import HfApi

        return HfApi().model_info(model_name).sha
    except Exception:
        return None
