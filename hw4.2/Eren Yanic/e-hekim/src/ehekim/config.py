"""Central configuration.

Security note
------------
This module deliberately does **not** read any LLM provider API key from the
environment. The web application is designed so that provider credentials are
supplied per-request by the end user and never persisted server-side. The
``.env`` file is used only by the offline operator scripts in ``scripts/``
(dataset ingestion and Hugging Face upload), which import
:func:`operator_secrets` explicitly.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --- Embedding model -------------------------------------------------------
# magibu/embeddingmagibu-200m is an asymmetric (prompt-conditioned) model:
# queries and documents must be encoded with different instruction prefixes.
# These strings are copied verbatim from the model's
# `config_sentence_transformers.json` ("query" and "document" prompts) so that
# ingestion, querying and benchmarking can never drift apart.
EMBEDDING_MODEL_ID = "magibu/embeddingmagibu-200m"
EMBEDDING_DIM = 768
QUERY_PROMPT = "task: search result | query: "
DOCUMENT_PROMPT_TEMPLATE = "title: {title} | text: "
DOCUMENT_TITLE_FALLBACK = "none"

# --- Source dataset --------------------------------------------------------
SOURCE_DATASET_ID = "umutertugrul/turkish-hospital-medical-articles"
HOSPITAL_SPLITS = (
    "acibadem",
    "anadolusaglik",
    "atlas",
    "baskentistanbul",
    "bayindir",
    "florence",
    "guven",
    "liv",
    "medicalpark",
    "medicalpoint",
    "medicana",
    "medipol",
    "memorial",
    "yeditepe",
)
TARGET_ARTICLE_COUNT = 1000
MIN_ARTICLE_CHARS = 400  # drop stubs / navigation-only scrapes

# --- Chunking --------------------------------------------------------------
CHUNK_TARGET_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64
CHUNK_MIN_TOKENS = 32  # discard slivers that carry no retrievable meaning

# --- Retrieval defaults ----------------------------------------------------
# Selected by the sweep in `scripts/benchmark.py` (see data/threshold_report.md).
# On the 30-question evaluation set the lowest-scoring positive lands at 0.5819
# and the highest-scoring negative at 0.4777; every threshold in [0.50, 0.58]
# separates them perfectly. 0.53 is the midpoint of that plateau, which keeps
# the operating point as far as possible from both failure modes.
DEFAULT_SIMILARITY_THRESHOLD = 0.53
DEFAULT_TOP_K = 5
MAX_TOP_K = 20

# Two independent refusal layers, deliberately worded differently so that logs,
# tests and the UI can tell which one fired.
#
# Layer 1 — retrieval gate. Emitted by our own code when the best match falls
# below the similarity threshold. The LLM is never invoked, so it cannot
# hallucinate. This is the sentence the assignment specifies.
REFUSAL_MESSAGE_TR = "Bu sorunun cevabı belgelerimde bulunmamaktadır."
REFUSAL_MESSAGE_EN = "The answer to this question is not found in my documents."

# Layer 2 — model gate. Chunks cleared the threshold (they are topically close)
# but do not actually contain the answer. A similarity score cannot detect this:
# "Hodgkin lenfoma nedir?" and "Hodgkin lenfomada 5 yıllık sağkalım oranı
# nedir?" retrieve the same chunk with a high score, yet only the first is
# answerable from it. So the model is instructed to refuse with this exact
# sentence rather than fill the gap from its pretrained knowledge.
MODEL_REFUSAL_MESSAGE_TR = "Bu bilgiyi bilmiyorum; bu konuda size yardımcı olamıyorum."
MODEL_REFUSAL_MESSAGE_EN = "I do not know this information; I cannot help you with this."

# --- Prompt-injection hardening -------------------------------------------
MAX_QUERY_CHARS = 1000


class Settings(BaseSettings):
    """Runtime settings for the API server (no secrets)."""

    model_config = SettingsConfigDict(env_prefix="EHEKIM_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    chroma_dir: Path = Field(default=PROJECT_ROOT / "chroma_db")
    collection_name: str = "ehekim_chunks"
    embedding_device: str | None = None  # None -> auto (cuda if available)
    embedding_batch_size: int = 32
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    top_k: int = DEFAULT_TOP_K
    # Upstream call budget; keeps a hung provider from pinning a worker.
    llm_timeout_seconds: float = 180.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def operator_secrets() -> dict[str, str | None]:
    """Load operator-only secrets from ``.env`` for offline scripts.

    Never called by the API server. Returns the values without logging them.
    """
    from dotenv import dotenv_values

    values = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    return {
        "HUGGINGFACE_TOKEN": values.get("HUGGINGFACE_TOKEN"),
        "DEEPSEEK_API_KEY": values.get("DEEPSEEK_API_KEY"),
    }
