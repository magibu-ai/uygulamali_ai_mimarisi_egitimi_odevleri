#!/usr/bin/env python3
"""Assign a deterministic, difficulty-balanced public/private split.

The public (HuggingFace dev) sample should be a representative cross-section, not
all of one difficulty. This script marks exactly one item per file as `public`,
choosing the difficulty by (language, format) so that, per discipline, the public
sample spans L1–L4 evenly:

    (tr, multiple_choice) -> one L1 item
    (tr, short_answer)    -> one L2 item
    (en, multiple_choice) -> one L3 item
    (en, short_answer)    -> one L4 item

That yields 1 public item per file = 4 per discipline = 80 total (~10%), balanced
20 items per difficulty tier. Everything else becomes `private`. Idempotent.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

TARGET = {
    ("tr", "multiple_choice"): "L1",
    ("tr", "short_answer"): "L2",
    ("en", "multiple_choice"): "L3",
    ("en", "short_answer"): "L4",
}


def main():
    changed = 0
    for dirpath, _, filenames in os.walk(DATA_DIR):
        for fn in sorted(filenames):
            if not fn.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
            if not records:
                continue
            lang = records[0]["language"]
            fmt = records[0]["format"]
            target = TARGET.get((lang, fmt))
            picked = False
            for rec in records:
                if not picked and target is not None and rec["difficulty"] == target:
                    new = "public"
                    picked = True
                else:
                    new = "private"
                if rec.get("split") != new:
                    changed += 1
                rec["split"] = new
            with open(path, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Split alanları güncellendi (değişen kayıt: {changed}).")


if __name__ == "__main__":
    main()
