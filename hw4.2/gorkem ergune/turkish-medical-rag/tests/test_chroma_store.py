"""Phase 4 tests: vector-store logic without a running ChromaDB.

Pure helpers plus a fake collection injected into ChromaStore cover the
distance→similarity conversion, metadata, formatting, top-k, and guards.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.config import load_config
from src.embeddings.embedder import assert_embeddings_valid, l2_normalize
from src.vectorstore.chroma_store import (
    ChromaStore,
    build_metadata,
    check_unique_ids,
    distance_to_similarity,
    format_search_results,
)


# --- configuration -------------------------------------------------------- #

def test_config_vectorstore_and_topk():
    cfg = load_config()
    assert cfg["vectorstore"]["distance"] == "cosine"
    assert cfg["vectorstore"]["collection_name"]
    assert cfg["vectorstore"]["persist_path"]
    assert isinstance(cfg["retrieval"]["top_k"], int)
    assert cfg["retrieval"]["top_k"] > 0


# --- distance -> similarity ---------------------------------------------- #

def test_distance_to_similarity_basic():
    assert distance_to_similarity(0.0) == 1.0
    assert distance_to_similarity(1.0) == 0.0
    assert distance_to_similarity(0.25) == 0.75


def test_similarity_conversion_in_results():
    result = {
        "ids": [["c1", "c2"]],
        "distances": [[0.1, 0.4]],
        "documents": [["metin1", "metin2"]],
        "metadatas": [[
            {"url": "u1", "title": "t1", "source": "acibadem", "parent_id": "doc_1"},
            {"url": "u2", "title": "t2", "source": "memorial", "parent_id": "doc_2"},
        ]],
    }
    out = format_search_results(result)
    assert out[0]["similarity"] == pytest.approx(0.9)
    assert out[1]["similarity"] == pytest.approx(0.6)


# --- metadata ------------------------------------------------------------- #

def test_build_metadata_fields_and_no_text_duplication():
    chunk = {
        "chunk_id": "doc_1_chunk_000", "parent_id": "doc_1",
        "url": "https://x", "title": "Başlık", "source": "acibadem",
        "chunk_text": "uzun metin",
    }
    md = build_metadata(chunk)
    assert md == {"url": "https://x", "title": "Başlık",
                  "source": "acibadem", "parent_id": "doc_1"}
    assert "chunk_text" not in md


def test_build_metadata_missing_title_safe():
    md = build_metadata({"url": "u", "title": None, "source": "s", "parent_id": "p"})
    assert md["title"] == ""


# --- result formatting / ranking ----------------------------------------- #

def test_format_search_results_structure():
    result = {
        "ids": [["a", "b"]],
        "distances": [[0.2, 0.3]],
        "documents": [["da", "db"]],
        "metadatas": [[
            {"url": "u", "title": "t", "source": "s", "parent_id": "p"},
            {"url": "u2", "title": "t2", "source": "s2", "parent_id": "p2"},
        ]],
    }
    out = format_search_results(result)
    assert [r["rank"] for r in out] == [1, 2]
    assert set(out[0]) == {
        "rank", "chunk_id", "similarity", "chunk_text",
        "url", "title", "source", "parent_id",
    }
    assert out[0]["chunk_text"] == "da"
    assert out[1]["parent_id"] == "p2"


# --- unique-id guard ------------------------------------------------------ #

def test_check_unique_ids_ok():
    check_unique_ids(["a", "b", "c"])


def test_check_unique_ids_detects_duplicates():
    with pytest.raises(ValueError, match="Duplicate"):
        check_unique_ids(["a", "b", "a"])


# --- ingestion invariants (reused embedder validators) ------------------- #

def test_invalid_dimension_rejected():
    v = l2_normalize(np.random.default_rng(0).normal(size=(4, 512)).astype(np.float32))
    with pytest.raises(ValueError, match="dimension"):
        assert_embeddings_valid(v, expected_dim=1024)


def test_nan_inf_rejected():
    v = l2_normalize(np.random.default_rng(0).normal(size=(3, 8)).astype(np.float32))
    v[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        assert_embeddings_valid(v, expected_dim=8)
    v2 = l2_normalize(np.random.default_rng(1).normal(size=(3, 8)).astype(np.float32))
    v2[1, 1] = np.inf
    with pytest.raises(ValueError, match="infinite"):
        assert_embeddings_valid(v2, expected_dim=8)


# --- top-k search via a fake collection (no real ChromaDB) --------------- #

class FakeCollection:
    """Minimal stand-in exposing the query() shape ChromaStore expects."""

    def __init__(self, ids, distances, documents, metadatas):
        self._data = (ids, distances, documents, metadatas)

    def query(self, query_embeddings, n_results, include):
        ids, dists, docs, metas = self._data
        return {
            "ids": [ids[:n_results]],
            "distances": [dists[:n_results]],
            "documents": [docs[:n_results]],
            "metadatas": [metas[:n_results]],
        }


def test_search_respects_top_k_and_conversion():
    store = ChromaStore(persist_path="x", collection_name="c", space="cosine")
    store.collection = FakeCollection(
        ids=["a", "b", "c", "d"],
        distances=[0.05, 0.2, 0.5, 0.9],
        documents=["da", "db", "dc", "dd"],
        metadatas=[{"url": "u", "title": "t", "source": "s", "parent_id": "p"}] * 4,
    )
    out = store.search(np.zeros(1024, dtype=np.float32), top_k=2)
    assert len(out) == 2
    assert out[0]["chunk_id"] == "a"
    assert out[0]["similarity"] == pytest.approx(0.95)
    assert out[0]["rank"] == 1
