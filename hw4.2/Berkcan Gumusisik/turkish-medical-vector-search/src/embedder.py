"""Shared embedding helpers for the magibu/embeddingmagibu-200m model.

The model is asymmetric (EmbeddingGemma-style): documents and queries use
different prompt templates baked into its ``config_sentence_transformers.json``:

    query    -> "task: search result | query: "
    document -> "title: none | text: "

Encoding each side with the correct prompt is what makes retrieval work well, so
this module is the single place both indexing and search go through. The model
also ends in a Normalize layer, so outputs are unit vectors and the dot product
equals cosine similarity.
"""
from functools import lru_cache
from typing import List

import numpy as np

from config import EMBED_MODEL, NORMALIZE


@lru_cache(maxsize=1)
def get_model():
    """Load (once) and cache the SentenceTransformer model."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def get_tokenizer():
    """Return a ``str -> token count`` callable using the model's tokenizer."""
    tok = get_model().tokenizer

    def count(text: str) -> int:
        return len(tok.encode(text, add_special_tokens=False))

    return count


def embed_documents(texts: List[str], batch_size: int = 32) -> np.ndarray:
    """Encode chunk texts with the *document* prompt."""
    model = get_model()
    return model.encode(
        texts,
        prompt_name="document",
        batch_size=batch_size,
        normalize_embeddings=NORMALIZE,
        convert_to_numpy=True,
        show_progress_bar=True,
    )


def embed_query(text: str) -> np.ndarray:
    """Encode a single question with the *query* prompt. Returns a 1-D vector."""
    model = get_model()
    vec = model.encode(
        [text],
        prompt_name="query",
        normalize_embeddings=NORMALIZE,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vec[0]
