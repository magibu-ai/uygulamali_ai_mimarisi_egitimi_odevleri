"""CLI demo smoke tests — offline, using a fake pipeline (no model/DB/LLM)."""
from __future__ import annotations

import importlib

chat = importlib.import_module("scripts.chat")


class FakePipeline:
    """Stand-in for RAGPipeline: records questions, returns a preset result."""

    def __init__(self, result):
        self._result = result
        self.calls = []

    def answer(self, question):
        self.calls.append(question)
        return {**self._result, "question": question}


ACCEPTED = {
    "top_similarity": 0.7241, "threshold": 0.575, "accepted": True,
    "llm_called": True, "answer": "Anemi kırmızı kan hücresi eksikliğidir.",
    "retrieved_chunk_ids": ["c1"],
    "sources": [{
        "chunk_id": "doc_00000_chunk_000", "parent_id": "doc_00000",
        "title": "Anemi Nedir?", "url": "https://example.com/anemi",
        "source": "atlas", "similarity": 0.7241,
    }],
}

REJECTED = {
    "top_similarity": 0.42, "threshold": 0.575, "accepted": False,
    "llm_called": False,
    "answer": "Bu sorunun cevabı dokümanlarımda yer almamaktadır.",
    "retrieved_chunk_ids": ["c9"], "sources": [],
}


def test_format_accepted_shows_answer_similarity_and_sources():
    out = chat.format_result({**ACCEPTED, "question": "Anemi nedir?"})
    assert "KABUL" in out
    assert "LLM çağrıldı" in out
    assert "Anemi kırmızı kan hücresi eksikliğidir." in out
    assert "0.7241" in out          # similarity
    assert "0.575" in out           # threshold
    assert "Anemi Nedir?" in out    # source title
    assert "https://example.com/anemi" in out
    assert "doc_00000_chunk_000" in out


def test_format_rejected_shows_message_and_no_llm():
    out = chat.format_result({**REJECTED, "question": "Kleptomani nedir?"})
    assert "REDDEDİLDİ" in out
    assert "LLM çağrılmadı" in out
    assert "Bu sorunun cevabı dokümanlarımda yer almamaktadır." in out
    assert "0.42" in out and "0.575" in out


def test_run_once_calls_pipeline_once_and_prints():
    fake = FakePipeline(ACCEPTED)
    captured: list[str] = []
    chat.run_once(fake, "Anemi nedir?", out=captured.append)
    assert fake.calls == ["Anemi nedir?"]
    assert any("Cevap:" in c for c in captured)


def test_interactive_exits_cleanly_on_ctrl_c():
    fake = FakePipeline(REJECTED)

    def fake_input(_prompt):
        raise KeyboardInterrupt

    captured: list[str] = []
    chat.interactive(fake, in_=fake_input, out=captured.append)  # must not raise
    assert fake.calls == []
    assert any("Çıkılıyor" in c for c in captured)


def test_interactive_answers_question_then_eof():
    fake = FakePipeline(ACCEPTED)
    seq = iter(["Anemi nedir?"])

    def fake_input(_prompt):
        try:
            return next(seq)
        except StopIteration:
            raise EOFError

    captured: list[str] = []
    chat.interactive(fake, in_=fake_input, out=captured.append)
    assert "Anemi nedir?" in fake.calls
    assert any("KABUL" in c for c in captured)


def test_interactive_quit_keyword_exits():
    fake = FakePipeline(ACCEPTED)
    seq = iter(["çık"])

    def fake_input(_prompt):
        return next(seq)

    captured: list[str] = []
    chat.interactive(fake, in_=fake_input, out=captured.append)
    assert fake.calls == []  # 'çık' should not reach the pipeline
    assert any("Çıkılıyor" in c for c in captured)
