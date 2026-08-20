"""MIHENK otomatik puanlama (Bölüm 8).

Kullanım:
    from scoring.score import score_item
    score_item(question_record, model_output_str) -> 0 veya 1

MC: model çıktısından seçilen harf regex ile ayrıştırılır; doğru harfle birebir
    eşleşme 1 puan.
Short answer: normalize edilmiş metin kanonik cevap/eş anlamlılarla karşılaştırılır;
    sayısal cevaplarda tolerans; 7 kelimeyi aşan yanıt otomatik 0 puan.
"""
from __future__ import annotations

import re
from typing import Optional

try:
    from .normalize import normalize_text, word_count, numbers_match, try_parse_number
except ImportError:  # doğrudan çalıştırma
    from normalize import normalize_text, word_count, numbers_match, try_parse_number

MAX_SHORT_ANSWER_WORDS = 7

# "Cevap: C", "(C)", "C)", "C.", "answer is C" gibi kalıplardan harfi çeker.
_MC_LETTER_RE = re.compile(r"\b([A-E])\b")


def extract_mc_letter(model_output: str) -> Optional[str]:
    if not model_output:
        return None
    text = model_output.strip()
    # Öncelik: son satırdaki tek harf ya da "cevap/answer: X" kalıbı
    m = re.search(r"(?:cevap|answer|yanıt)\s*[:\-]?\s*\(?([A-E])\)?", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Tek başına bırakılmış harf(ler) — sonuncuyu al
    letters = _MC_LETTER_RE.findall(text.upper())
    if letters:
        return letters[-1]
    return None


def score_mc(record: dict, model_output: str) -> int:
    predicted = extract_mc_letter(model_output)
    return 1 if predicted is not None and predicted == record.get("answer") else 0


def score_short(record: dict, model_output: str) -> int:
    if model_output is None:
        return 0
    raw = model_output.strip()
    # Format dışı / çok uzun yanıt: talimata uymama -> 0
    if word_count(raw) > MAX_SHORT_ANSWER_WORDS:
        return 0
    candidates = [record.get("answer_short", "")]
    candidates += list(record.get("answer_aliases", []) or [])
    norm_pred = normalize_text(raw)
    for cand in candidates:
        if not cand:
            continue
        if normalize_text(cand) == norm_pred:
            return 1
        if numbers_match(cand, raw):
            return 1
    return 0


def score_item(record: dict, model_output: str) -> int:
    fmt = record.get("format")
    if fmt == "multiple_choice":
        return score_mc(record, model_output)
    if fmt == "short_answer":
        return score_short(record, model_output)
    raise ValueError(f"Bilinmeyen format: {fmt}")
