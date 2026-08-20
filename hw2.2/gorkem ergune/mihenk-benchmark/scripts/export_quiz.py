#!/usr/bin/env python3
"""Export MIHENK items as a plain quiz you can paste into any chat LLM.

Produces a human/LLM-readable document: numbered questions (with options for
multiple choice), a short instruction header, and the ANSWER KEY at the very
bottom so you can grade the model's replies.

Usage:
    python scripts/export_quiz.py --split public --language tr --output quiz_tr.md
    python scripts/export_quiz.py --split public --language en --output quiz_en.md
    python scripts/export_quiz.py --split all --language tr --limit 20 --output quiz.md
"""
from __future__ import annotations

import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

HEADER = {
    "tr": (
        "# MIHENK Testi\n\n"
        "Aşağıdaki soruları yanıtla. **Çoktan seçmeli** sorularda YALNIZCA doğru şıkkın "
        "harfini (A–E) yaz; **kısa cevaplı** sorularda YALNIZCA cevabı (en fazla 7 kelime) "
        "yaz. Açıklama ekleme. Her yanıtı soru numarasıyla ver (örn. `1. C`).\n"
    ),
    "en": (
        "# MIHENK Quiz\n\n"
        "Answer the questions below. For **multiple-choice** items write ONLY the correct "
        "option letter (A–E); for **short-answer** items write ONLY the answer (at most 7 "
        "words). Do not explain. Give each reply with its question number (e.g. `1. C`).\n"
    ),
}
KEY_TITLE = {"tr": "CEVAP ANAHTARI", "en": "ANSWER KEY"}
SA_HINT = {"tr": "(kısa cevap)", "en": "(short answer)"}


def iter_records(split: str, language: str):
    for dirpath, _, filenames in os.walk(DATA_DIR):
        for fn in sorted(filenames):
            if not fn.endswith(".jsonl"):
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    if (split == "all" or r.get("split") == split) and r["language"] == language:
                        yield r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["public", "private", "all"], default="public")
    ap.add_argument("--language", choices=["tr", "en"], default="tr")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    lang = args.language
    records = list(iter_records(args.split, lang))
    # stable, readable order: discipline, then difficulty, then id
    records.sort(key=lambda r: (r["discipline"], r["difficulty"], r["id"]))
    if args.limit:
        records = records[: args.limit]
    if not records:
        raise SystemExit("Seçilen ölçütlerde soru bulunamadı.")

    lines = [HEADER[lang], "\n---\n"]
    key = []
    for i, r in enumerate(records, 1):
        head = f"**{i}.** [{r['discipline']} · {r['difficulty']}] {r['question']}"
        lines.append(head)
        if r["format"] == "multiple_choice":
            for k, v in r["choices"].items():
                lines.append(f"- {k}) {v}")
            key.append(f"{i}. {r['answer']}")
        else:
            lines.append(f"_{SA_HINT[lang]}_")
            ans = r["answer_short"]
            aliases = r.get("answer_aliases") or []
            key.append(f"{i}. {ans}" + (f"  (kabul: {', '.join(aliases)})" if aliases else ""))
        lines.append("")  # blank line between questions

    lines.append("\n\n---\n")
    lines.append(f"## {KEY_TITLE[lang]}\n")
    lines.append("```")
    lines.extend(key)
    lines.append("```")

    out = os.path.join(ROOT, args.output) if not os.path.isabs(args.output) else args.output
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(records)} soru yazıldı: {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
