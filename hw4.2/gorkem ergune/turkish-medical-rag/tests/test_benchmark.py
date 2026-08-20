"""Phase 5 tests: enforce the official benchmark's integrity.

Reads the frozen data/benchmark/benchmark.json and the corpus chunks; validates
structure, counts, evidence grounding, and metadata consistency. Model-free.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

from src.config import load_config, resolve_path

# Diagnostic pilot queries (Phase-3/4) — must NOT appear in the benchmark.
PILOT_QUERIES = {
    "Hipertansiyon belirtileri nelerdir?",
    "Diyabet nasıl tedavi edilir?",
    "Uyku apnesi nedir ve nedenleri nelerdir?",
    "Bel fıtığı ameliyatı sonrası iyileşme süreci nasıldır?",
    "Gut hastalığının belirtileri nelerdir?",
    "Tüp bebek tedavisi nasıl yapılır?",
    "Sedef hastalığı nedir ve nasıl tedavi edilir?",
    "Kalp yetmezliği belirtileri nelerdir?",
    "Gastroenterit neden olur?",
    "Türkiye'nin başkenti hangi şehirdir?",
    "Python programlama dilinde bir liste nasıl ters çevrilir?",
    "2022 Dünya Kupası'nı hangi ülke kazandı?",
}


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def benchmark(config):
    path = resolve_path(config["paths"]["data_benchmark"]) / "benchmark.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def chunks_by_id(config):
    path = resolve_path(config["chunking"]["chunks_output"])
    by_id = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            by_id[r["chunk_id"]] = r
    return by_id


def _questions(benchmark):
    return benchmark["questions"]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --- counts --------------------------------------------------------------- #

def test_exactly_30_questions(benchmark):
    assert len(_questions(benchmark)) == 30


def test_20_positive_10_negative(benchmark):
    qs = _questions(benchmark)
    assert sum(q["type"] == "positive" for q in qs) == 20
    assert sum(q["type"] == "negative" for q in qs) == 10


def test_metadata_counts_match(benchmark):
    md = benchmark["metadata"]
    assert md["positive_count"] == 20
    assert md["negative_count"] == 10
    assert md["total_count"] == 30
    assert md["selected_document_count"] == 300
    assert md["chunk_count"] == 2072
    assert md["benchmark_version"]


# --- ids / questions ------------------------------------------------------ #

def test_unique_question_ids(benchmark):
    ids = [q["id"] for q in _questions(benchmark)]
    assert len(ids) == len(set(ids))


def test_questions_non_empty(benchmark):
    for q in _questions(benchmark):
        assert q["question"].strip()


def test_no_duplicate_questions(benchmark):
    texts = [_norm(q["question"]) for q in _questions(benchmark)]
    assert len(texts) == len(set(texts))


def test_pilot_queries_absent(benchmark):
    texts = {_norm(q["question"]) for q in _questions(benchmark)}
    assert texts.isdisjoint({_norm(p) for p in PILOT_QUERIES})


# --- positive grounding --------------------------------------------------- #

def test_positive_chunk_ids_exist_and_evidence_grounded(benchmark, chunks_by_id):
    for q in _questions(benchmark):
        if q["type"] != "positive":
            continue
        assert q["expected_chunk_ids"], q["id"]
        for cid in q["expected_chunk_ids"]:
            assert cid in chunks_by_id, f"{q['id']} references missing chunk {cid}"
        # evidence must be an (whitespace-normalized) excerpt of the referenced chunk
        chunk = chunks_by_id[q["expected_chunk_ids"][0]]
        assert _norm(q["evidence"]) in _norm(chunk["chunk_text"]), q["id"]


def test_positive_urls_and_parents_match_source(benchmark, chunks_by_id):
    for q in _questions(benchmark):
        if q["type"] != "positive":
            continue
        chunk = chunks_by_id[q["expected_chunk_ids"][0]]
        assert q["expected_urls"] == [chunk["url"]], q["id"]
        assert q["expected_parent_ids"] == [chunk["parent_id"]], q["id"]
        assert q["verification"]["answer_present"] is True


# --- negatives ------------------------------------------------------------ #

def test_negatives_have_no_expected_chunks(benchmark):
    for q in _questions(benchmark):
        if q["type"] != "negative":
            continue
        assert q["expected_chunk_ids"] == []
        assert q["expected_parent_ids"] == []
        assert q["verification"]["answer_present"] is False
        assert q["verification"]["lexical_hits"] == 0


def test_negative_topics_absent_from_corpus(benchmark, chunks_by_id):
    blob = "\n".join(c["chunk_text"] for c in chunks_by_id.values()).casefold()
    for q in _questions(benchmark):
        if q["type"] != "negative":
            continue
        for kw in q["verification"]["lexical_keywords"]:
            assert blob.count(kw.casefold()) == 0, f"{q['id']} keyword '{kw}' present"


# --- utf-8 ---------------------------------------------------------------- #

def test_utf8_integrity(benchmark):
    for q in _questions(benchmark):
        blob = q["question"] + q.get("evidence", "")
        assert "�" not in blob
        blob.encode("utf-8").decode("utf-8")  # round-trips
