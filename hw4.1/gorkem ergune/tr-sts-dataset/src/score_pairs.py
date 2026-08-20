# -*- coding: utf-8 -*-
"""
magibu/embeddingmagibu-200m ile cumle cifti benzerlik puanlama.
HuggingFace Space ile ayni yontem: SentenceTransformer + normalize edilmis
embedding + cosine similarity (dot / (||a||*||b||)).
"""
import re
import sys
import csv
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_ID = "magibu/embeddingmagibu-200m"
IN_PATH = "cümleler.txt"
OUT_TXT = "sonuclar.txt"
OUT_CSV = "sonuclar.csv"

NUM_RE = re.compile(r"^-?\d+[.,]\d+$|^-?\d+$")


def is_score_line(line: str) -> bool:
    return bool(NUM_RE.match(line.strip()))


def parse_pairs(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    blocks = re.split(r"\n\s*\n", raw)
    pairs = []
    for block in blocks:
        # bos olmayan, skor olmayan satirlar = cumleler
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        sents = [ln for ln in lines if not is_score_line(ln)]
        if len(sents) >= 2:
            pairs.append((sents[0], sents[1]))
        elif len(sents) == 1:
            # tek cumlelik blok (not/aciklama) - atla
            continue
    return pairs


def cosine_similarity(a, b):
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def main():
    pairs = parse_pairs(IN_PATH)
    print(f"{len(pairs)} cumle cifti bulundu. Model yukleniyor...", flush=True)

    model = SentenceTransformer(MODEL_ID)
    print("Model yuklendi. Puanlaniyor...", flush=True)

    results = []
    for i, (s1, s2) in enumerate(pairs, 1):
        emb = model.encode([s1, s2], normalize_embeddings=True,
                           convert_to_numpy=True, show_progress_bar=False)
        score = cosine_similarity(emb[0], emb[1])
        results.append((s1, s2, score))
        print(f"[{i:>2}] {score:.4f}  |  {s1[:45]}", flush=True)

    # TXT ciktisi (orijinal format: cumle / cumle / skor)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        for s1, s2, score in results:
            f.write(f"{s1}\n{s2}\n{str(round(score, 10)).replace('.', ',')}\n\n")

    # CSV ciktisi (stsb-tr tarzi: sentence1, sentence2, score)
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sentence1", "sentence2", "score"])
        for s1, s2, score in results:
            w.writerow([s1, s2, round(score, 6)])

    print(f"\nBitti. -> {OUT_TXT} ve {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
