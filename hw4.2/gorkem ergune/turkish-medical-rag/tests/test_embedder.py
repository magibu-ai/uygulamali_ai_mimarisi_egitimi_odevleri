"""Phase 3 tests: embedding logic (no model download required).

All model-backed behaviour is covered by pure helpers with injected
dependencies (fake tokenizer, synthetic vectors), so the suite stays fast and
offline.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.config import load_config
from src.embeddings.embedder import (
    assert_embeddings_valid,
    check_alignment,
    find_overlength_chunks,
    format_document,
    format_query,
    l2_normalize,
)

INSTRUCTION = ("Given a Turkish search query, retrieve relevant passages "
               "written in Turkish that best answer the query")


# --- configuration -------------------------------------------------------- #

def test_config_locks_model_and_dimension():
    cfg = load_config()["embedding"]
    assert cfg["model_name"] == "ytu-ce-cosmos/turkish-e5-large"
    assert cfg["expected_dim"] == 1024
    assert cfg["normalize"] is True
    assert cfg["query_instruction"] == INSTRUCTION


# --- encoding format (single source of truth) ----------------------------- #

def test_query_formatting_is_exact():
    q = format_query("Hipertansiyon belirtileri nelerdir?", INSTRUCTION)
    assert q == (
        "Instruct: Given a Turkish search query, retrieve relevant passages "
        "written in Turkish that best answer the query\n"
        "Query: Hipertansiyon belirtileri nelerdir?"
    )


def test_document_formatting_is_raw():
    assert format_document("Bir tıbbi metin.") == "Bir tıbbi metin."


# --- normalization -------------------------------------------------------- #

def test_l2_normalize_gives_unit_norms():
    rng = np.random.default_rng(0)
    vecs = rng.normal(size=(5, 8)).astype(np.float32) * 10.0
    out = l2_normalize(vecs)
    norms = np.linalg.norm(out, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)
    assert out.dtype == np.float32


def test_l2_normalize_handles_zero_row():
    vecs = np.zeros((2, 4), dtype=np.float32)
    out = l2_normalize(vecs)
    assert np.isfinite(out).all()


# --- validation ----------------------------------------------------------- #

def _unit(n, d, seed=1):
    rng = np.random.default_rng(seed)
    return l2_normalize(rng.normal(size=(n, d)).astype(np.float32))


def test_valid_embeddings_pass():
    stats = assert_embeddings_valid(_unit(10, 1024), expected_dim=1024)
    assert stats["norm_max_abs_deviation"] < 1e-3


def test_wrong_dimension_raises():
    with pytest.raises(ValueError, match="dimension"):
        assert_embeddings_valid(_unit(3, 768), expected_dim=1024)


def test_nan_detected():
    v = _unit(3, 4)
    v[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        assert_embeddings_valid(v, expected_dim=4)


def test_inf_detected():
    v = _unit(3, 4)
    v[1, 1] = np.inf
    with pytest.raises(ValueError, match="infinite"):
        assert_embeddings_valid(v, expected_dim=4)


def test_non_normalized_detected():
    v = _unit(3, 4) * 2.0  # norms == 2
    with pytest.raises(ValueError, match="normalized"):
        assert_embeddings_valid(v, expected_dim=4)


# --- alignment ------------------------------------------------------------ #

def test_alignment_ok():
    check_alignment(["a", "b", "c"], _unit(3, 4))


def test_alignment_mismatch_raises():
    with pytest.raises(ValueError, match="Alignment"):
        check_alignment(["a", "b"], _unit(3, 4))


def test_alignment_order_is_positional():
    ids = [f"doc_{i:05d}_chunk_000" for i in range(4)]
    vecs = _unit(4, 4)
    mapping = dict(zip(ids, vecs))
    # positional pairing must be stable/deterministic
    assert list(mapping.keys()) == ids
    assert np.array_equal(mapping[ids[2]], vecs[2])


# --- context-length validation (injected fake tokenizer) ------------------ #

def test_find_overlength_flags_offenders():
    ids = ["c0", "c1", "c2"]
    texts = ["short", "way too long text", "medium"]
    # fake tokenizer: token count == word count
    count = lambda t: len(t.split())
    offenders = find_overlength_chunks(ids, texts, count, max_length=2)
    assert [o["chunk_id"] for o in offenders] == ["c1"]
    assert offenders[0]["tokens"] == 4


def test_find_overlength_empty_when_all_fit():
    ids = ["c0", "c1"]
    texts = ["a b", "c d"]
    count = lambda t: len(t.split())
    assert find_overlength_chunks(ids, texts, count, max_length=5) == []
