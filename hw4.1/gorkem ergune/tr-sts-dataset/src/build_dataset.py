# -*- coding: utf-8 -*-
"""
Build a Turkish STS (semantic textual similarity) dataset.

Sources:
  - cümleler.txt        (plain text: sentence / sentence / [old score] blocks)
  - embedding.docx      (Word doc with additional sentence pairs)

Pairs from both are merged + de-duplicated, then RE-SCORED locally with
magibu/embeddingmagibu-200m (same method as the HF Space:
SentenceTransformer + normalized embeddings + cosine similarity).

Outputs (English names):
  - dataset/data.csv     -> sentence1, sentence2, score   (stsb-tr style)
  - results.txt          -> human-readable
"""
import os
import re
import csv
import unicodedata
import numpy as np
from sentence_transformers import SentenceTransformer
import docx

MODEL_ID = "magibu/embeddingmagibu-200m"
TXT_PATH = "cümleler.txt"
DOCX_PATH = "embedding.docx"
OUT_DIR = "dataset"
OUT_CSV = os.path.join(OUT_DIR, "data.csv")
OUT_TXT = "results.txt"

NUM_RE = re.compile(r"^-?\d+[.,]\d+$|^-?\d+$")


def is_score_line(line: str) -> bool:
    return bool(NUM_RE.match(line.strip()))


def norm(s: str) -> str:
    """Normalize a sentence for de-dup comparison (not for storage)."""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def clean(s: str) -> str:
    """Light cleanup for stored text (keep readable, fix artifacts)."""
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def pairs_from_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    out = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        sents = [ln for ln in lines if not is_score_line(ln)]
        if len(sents) >= 2:
            out.append((sents[0], sents[1]))
    return out


def pairs_from_docx(path):
    """Flatten every paragraph into lines; whenever a score line appears,
    the two preceding non-score lines form a pair. Handles the messy
    doc where sentences/scores got merged into single paragraphs."""
    d = docx.Document(path)
    lines = []
    for p in d.paragraphs:
        for ln in p.text.split("\n"):
            ln = ln.strip()
            if ln:
                lines.append(ln)
    out = []
    buf = []
    for ln in lines:
        if is_score_line(ln):
            if len(buf) >= 2:
                out.append((buf[-2], buf[-1]))
            buf = []
        else:
            buf.append(ln)
    return out


def cosine(a, b):
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return 0.0 if denom == 0 else float(np.dot(a, b) / denom)


def main():
    raw_pairs = pairs_from_txt(TXT_PATH) + pairs_from_docx(DOCX_PATH)

    # de-dup (order-preserving) on normalized text
    seen = set()
    pairs = []
    for s1, s2 in raw_pairs:
        c1, c2 = clean(s1), clean(s2)
        key = (norm(c1), norm(c2))
        rkey = (norm(c2), norm(c1))
        if not c1 or not c2 or c1 == c2 and norm(c1) == norm(c2) and key in seen:
            pass
        if key in seen or rkey in seen:
            continue
        seen.add(key)
        pairs.append((c1, c2))

    print(f"{len(raw_pairs)} ham cift -> {len(pairs)} benzersiz cift", flush=True)
    print("Model yukleniyor...", flush=True)
    model = SentenceTransformer(MODEL_ID)
    print("Puanlaniyor...\n", flush=True)

    results = []
    for i, (s1, s2) in enumerate(pairs, 1):
        emb = model.encode([s1, s2], normalize_embeddings=True,
                           convert_to_numpy=True, show_progress_bar=False)
        sc = cosine(emb[0], emb[1])
        results.append((s1, s2, sc))
        print(f"[{i:>2}] {sc:.4f} | {s1[:50]}", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sentence1", "sentence2", "score"])
        for s1, s2, sc in results:
            w.writerow([s1, s2, round(sc, 6)])

    with open(OUT_TXT, "w", encoding="utf-8") as f:
        for s1, s2, sc in results:
            f.write(f"{s1}\n{s2}\n{str(round(sc, 10)).replace('.', ',')}\n\n")

    print(f"\nToplam {len(results)} cift -> {OUT_CSV} , {OUT_TXT}", flush=True)


if __name__ == "__main__":
    main()
