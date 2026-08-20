#!/usr/bin/env python3
"""HuggingFace public sample split'ini oluşturur.

Kirlenmeyi (contamination) önlemek için HF'e yalnızca split=="public" kayıtları
gider; split=="private" holdout dağıtılmaz. Bu betik tüm data/ ağacını okur,
public kayıtları tek bir birleşik JSONL'e yazar ve istatistik üretir.

Çıktı:
    huggingface/data/mihenk_public.jsonl
    huggingface/stats.json
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
HF_DIR = os.path.join(ROOT, "huggingface")
OUT_JSONL = os.path.join(HF_DIR, "data", "mihenk_public.jsonl")
STATS_JSON = os.path.join(HF_DIR, "stats.json")


def iter_records():
    for dirpath, _, filenames in os.walk(DATA_DIR):
        for fn in sorted(filenames):
            if not fn.endswith(".jsonl"):
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)


def main():
    os.makedirs(os.path.dirname(OUT_JSONL), exist_ok=True)
    public, private = [], 0
    for rec in iter_records():
        if rec.get("split") == "public":
            public.append(rec)
        else:
            private += 1

    public.sort(key=lambda r: r["id"])
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for rec in public:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    stats = {
        "public_count": len(public),
        "private_count": private,
        "total": len(public) + private,
        "by_discipline": dict(Counter(r["discipline"] for r in public)),
        "by_language": dict(Counter(r["language"] for r in public)),
        "by_format": dict(Counter(r["format"] for r in public)),
        "by_difficulty": dict(Counter(r["difficulty"] for r in public)),
    }
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"public: {len(public)}  private(holdout, dağıtılmaz): {private}")
    print(f"yazıldı: {os.path.relpath(OUT_JSONL, ROOT)}")


if __name__ == "__main__":
    main()
