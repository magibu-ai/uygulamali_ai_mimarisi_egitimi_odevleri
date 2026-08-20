# -*- coding: utf-8 -*-
"""Combine real (dataset/data.csv, 39 pairs) + synthetic (synthetic.csv, 1000)
into the final HF dataset folder: hf_dataset/data.csv + README.md."""
import os
import csv
import random

random.seed(7)
OUT_DIR = "hf_dataset"
os.makedirs(OUT_DIR, exist_ok=True)

rows = []  # sentence1, sentence2, score, source, pair_type, topic

# real (manually collected) pairs
with open(os.path.join("dataset", "data.csv"), "r", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows.append([r["sentence1"], r["sentence2"], float(r["score"]),
                     "manual", "manual", ""])

# synthetic pairs
with open("synthetic.csv", "r", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows.append([r["sentence1"], r["sentence2"], float(r["score"]),
                     "synthetic", r["pair_type"], r["topic"]])

# drop degenerate (identical) pairs and exact duplicates (order-insensitive)
clean_rows, seen = [], set()
dropped_identical = dropped_dup = 0
for r in rows:
    s1, s2 = r[0].strip(), r[1].strip()
    if s1.lower() == s2.lower():
        dropped_identical += 1
        continue
    key = frozenset((s1.lower(), s2.lower()))
    if key in seen:
        dropped_dup += 1
        continue
    seen.add(key)
    clean_rows.append(r)
rows = clean_rows

random.shuffle(rows)

# 90/10 train/test split
n = len(rows)
n_test = max(1, round(n * 0.10))
for i, row in enumerate(rows):
    row.append("test" if i < n_test else "train")

header = ["sentence1", "sentence2", "score", "source", "pair_type", "topic", "split"]
# per-split files so datasets.load_dataset yields train/test (no redundant data.csv)
for split in ("train", "test"):
    with open(os.path.join(OUT_DIR, f"{split}.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows([r for r in rows if r[6] == split])

n_manual = sum(1 for r in rows if r[3] == "manual")
n_syn = sum(1 for r in rows if r[3] == "synthetic")
n_near0 = sum(1 for r in rows if r[2] < 0.2)
print(f"atilan: ozdes={dropped_identical} tekrar={dropped_dup}")
print(f"Toplam {n} cift | manual={n_manual} sentetik={n_syn} | "
      f"train={n-n_test} test={n_test} | 0.2 alti={n_near0}")
