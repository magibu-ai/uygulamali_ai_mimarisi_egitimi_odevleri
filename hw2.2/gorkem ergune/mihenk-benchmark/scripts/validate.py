#!/usr/bin/env python3
"""MIHENK veri seti doğrulayıcı.

- Tüm data/**/*.jsonl kayıtlarını şemaya ve MIHENK kurallarına karşı doğrular.
- jsonschema kuruluysa onu kullanır; değilse dahili manuel kontrolleri uygular.
- id benzersizliği, id/dosya-yolu tutarlılığı, tek doğru cevap, 7 kelime sınırı,
  disiplin içi tekrar eden soru metni gibi kuralları denetler.

Kullanım:
    python scripts/validate.py            # tüm veri
    python scripts/validate.py --stats    # sadece istatistik özeti
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SCHEMA_PATH = os.path.join(ROOT, "schema", "question_schema.json")
CONFIG_PATH = os.path.join(ROOT, "config", "disciplines.json")

sys.path.insert(0, os.path.join(ROOT, "scoring"))
from normalize import word_count  # noqa: E402

ID_RE = re.compile(r"^MIHENK-([A-Z]+)-(TR|EN)-(L[1-4])-([0-9]{4})$")
MAX_SHORT_WORDS = 7


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    by_slug = {d["slug"]: d for d in cfg["disciplines"]}
    by_abbr = {d["abbr"]: d for d in cfg["disciplines"]}
    return by_slug, by_abbr


def iter_records():
    for dirpath, _, filenames in os.walk(DATA_DIR):
        for fn in sorted(filenames):
            if not fn.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError as e:
                        yield rel, lineno, None, f"JSON parse hatası: {e}"
                        continue
                    yield rel, lineno, rec, None


def try_jsonschema():
    try:
        import jsonschema  # noqa
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        validator = jsonschema.Draft7Validator(schema)
        return validator
    except Exception:
        return None


def manual_checks(rec, rel, by_slug, by_abbr):
    """jsonschema yoksa temel yapısal kontroller."""
    errs = []
    req = ["id", "language", "discipline", "format", "difficulty", "question",
           "choices", "answer", "answer_short", "explanation", "tags",
           "source", "version_added", "split"]
    for k in req:
        if k not in rec:
            errs.append(f"eksik alan: {k}")
    if errs:
        return errs
    if rec["source"] != "orijinal-AI-üretim":
        errs.append(f"source hatalı: {rec['source']!r}")
    if rec["split"] not in ("public", "private"):
        errs.append(f"split hatalı: {rec['split']!r}")
    if rec["language"] not in ("tr", "en"):
        errs.append(f"language hatalı: {rec['language']!r}")
    if rec["difficulty"] not in ("L1", "L2", "L3", "L4"):
        errs.append(f"difficulty hatalı: {rec['difficulty']!r}")
    if rec["format"] == "multiple_choice":
        ch = rec.get("choices")
        if not isinstance(ch, dict) or not (4 <= len(ch) <= 5):
            errs.append("multiple_choice: choices 4-5 şık olmalı")
        elif rec.get("answer") not in ch:
            errs.append(f"answer {rec.get('answer')!r} choices içinde yok")
        if rec.get("answer_short") is not None:
            errs.append("multiple_choice: answer_short null olmalı")
    elif rec["format"] == "short_answer":
        if rec.get("choices") is not None or rec.get("answer") is not None:
            errs.append("short_answer: choices ve answer null olmalı")
        if not rec.get("answer_short"):
            errs.append("short_answer: answer_short boş")
        elif word_count(rec["answer_short"]) > MAX_SHORT_WORDS:
            errs.append(f"answer_short {word_count(rec['answer_short'])} kelime (>7)")
    return errs


def rule_checks(rec, rel, by_slug, by_abbr):
    errs = []
    m = ID_RE.match(rec.get("id", ""))
    if not m:
        errs.append(f"id formatı hatalı: {rec.get('id')!r}")
        return errs
    abbr, lang_u, diff, _seq = m.groups()
    # id <-> alan tutarlılığı
    if lang_u.lower() != rec.get("language"):
        errs.append(f"id dili ({lang_u}) language ({rec.get('language')}) ile uyumsuz")
    if diff != rec.get("difficulty"):
        errs.append(f"id zorluğu ({diff}) difficulty ile uyumsuz")
    if abbr not in by_abbr:
        errs.append(f"bilinmeyen disiplin kısaltması: {abbr}")
    else:
        exp_name = by_abbr[abbr]["name_tr"]
        if rec.get("discipline") != exp_name:
            errs.append(f"discipline {rec.get('discipline')!r} beklenen {exp_name!r} değil")
    # dosya yolu tutarlılığı: data/{lang}/{slug}/{format}.jsonl
    parts = rel.split("/")
    if len(parts) >= 4:
        _, path_lang, path_slug, fname = parts[-4], parts[-3], parts[-2], parts[-1]
        if path_lang != rec.get("language"):
            errs.append(f"dosya dili {path_lang} language ile uyumsuz")
        if path_slug in by_slug and by_slug[path_slug]["abbr"] != abbr:
            errs.append(f"dosya slug {path_slug} id kısaltması {abbr} ile uyumsuz")
        exp_fname = rec.get("format", "") + ".jsonl"
        if fname != exp_fname:
            errs.append(f"dosya adı {fname} format {rec.get('format')} ile uyumsuz")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    by_slug, by_abbr = load_config()
    validator = try_jsonschema()

    total = 0
    errors = []
    ids = {}
    per_file_questions = defaultdict(dict)
    stats = defaultdict(Counter)

    for rel, lineno, rec, parse_err in iter_records():
        loc = f"{rel}:{lineno}"
        if parse_err:
            errors.append(f"{loc}  {parse_err}")
            continue
        total += 1

        if validator is not None:
            for e in sorted(validator.iter_errors(rec), key=lambda x: x.path):
                errors.append(f"{loc}  şema: {e.message}")
        else:
            for e in manual_checks(rec, rel, by_slug, by_abbr):
                errors.append(f"{loc}  {e}")

        for e in rule_checks(rec, rel, by_slug, by_abbr):
            errors.append(f"{loc}  {e}")

        rid = rec.get("id")
        if rid in ids:
            errors.append(f"{loc}  tekrar eden id: {rid} (ilk: {ids[rid]})")
        else:
            ids[rid] = loc

        qnorm = (rec.get("question") or "").strip().lower()
        if qnorm in per_file_questions[rel]:
            errors.append(f"{loc}  aynı dosyada tekrar eden soru metni (ilk: {per_file_questions[rel][qnorm]})")
        else:
            per_file_questions[rel][qnorm] = loc

        stats["discipline"][rec.get("discipline")] += 1
        stats["language"][rec.get("language")] += 1
        stats["format"][rec.get("format")] += 1
        stats["difficulty"][rec.get("difficulty")] += 1
        stats["split"][rec.get("split")] += 1

    print(f"Toplam kayıt: {total}")
    print(f"Doğrulayıcı: {'jsonschema' if validator else 'dahili manuel'}")
    if args.stats or not errors:
        for dim in ("language", "format", "difficulty", "split"):
            print(f"  {dim}: {dict(sorted(stats[dim].items()))}")
        print(f"  disiplin sayısı: {len(stats['discipline'])}")

    if errors:
        print(f"\n{len(errors)} HATA:")
        for e in errors[:200]:
            print("  -", e)
        if len(errors) > 200:
            print(f"  ... ve {len(errors) - 200} tane daha")
        sys.exit(1)
    print("\nOK — tüm kayıtlar geçerli.")


if __name__ == "__main__":
    main()
