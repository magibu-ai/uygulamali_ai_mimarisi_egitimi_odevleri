---
license: gpl-3.0
language:
- tr
task_categories:
- sentence-similarity
- text-classification
tags:
- semantic-textual-similarity
- sts
- turkish
- news
- embeddings
pretty_name: Turkish STS (scored with magibu-200m)
size_categories:
- 1K<n<10K
configs:
- config_name: default
  data_files:
  - split: train
    path: train.csv
  - split: test
    path: test.csv
---

# Turkish STS — sentence pairs scored with `magibu/embeddingmagibu-200m`

A Turkish **Semantic Textual Similarity (STS)** dataset: each row is a pair of
sentences plus a similarity score. Scores come from the
[`magibu/embeddingmagibu-200m`](https://huggingface.co/magibu/embeddingmagibu-200m)
sentence-embedding model, computed as **cosine similarity over L2-normalized
embeddings** — the exact method used by the
[reference Space](https://huggingface.co/spaces/magibu/embeddingmagibu-200m).

The set deliberately spans the full similarity range, with **many near-zero
(unrelated) pairs**, so it can be used to evaluate or calibrate similarity
thresholds — not just high-similarity paraphrase detection.

---

## At a glance

| | |
|---|---|
| Total pairs | **1037** |
| Manually collected (`manual`) | 38 |
| Synthetic (`synthetic`) | 999 |
| Splits | train **933** / test **104** (90 / 10) |
| Language | Turkish (`tr`) |
| Score | cosine similarity, ≈ `-0.04` … `0.97` |

## Score distribution

| Score band | Pairs |
|---|---|
| 0.0 – 0.2 (unrelated) | 413 |
| 0.2 – 0.4 | 197 |
| 0.4 – 0.6 | 51 |
| 0.6 – 0.8 | 138 |
| 0.8 – 1.0 (near-identical) | 238 |

By pair type (synthetic):

| `pair_type` | n | mean | min | max |
|---|---|---|---|---|
| `unrelated` | 450 | 0.148 | −0.039 | 0.456 |
| `related` | 250 | 0.406 | 0.068 | 0.938 |
| `paraphrase` | 299 | 0.844 | 0.446 | 0.969 |

---

## Columns

| Column | Description |
|---|---|
| `sentence1`, `sentence2` | The two compared Turkish sentences |
| `score` | Cosine similarity from `magibu/embeddingmagibu-200m` |
| `source` | `manual` (hand-collected) or `synthetic` |
| `pair_type` | `manual` / `unrelated` / `related` / `paraphrase` |
| `topic` | Topic of the synthetic pair (for `unrelated`, both topics as `a\|b`) |
| `split` | `train` or `test` |

## Usage

```python
from datasets import load_dataset

ds = load_dataset("gorkemergune/stsb-tr")
print(ds)
print(ds["train"][0])

# e.g. keep only strongly-similar pairs
paraphrases = ds["train"].filter(lambda r: r["score"] >= 0.8)
```

---

## How it was built

**Manual pairs (38).** Real Turkish sentence pairs (news headlines and their
reworded versions) collected by hand and scored with the model.

**Synthetic pairs (999).** Template-generated sentences in the style of Turkish
news pages, across nine topics: **magazine/celebrity, sports, economy, politics,
weather, crime & accidents, health, technology, world**. Pairs are built at
three relatedness levels so scores span the whole range:

- `unrelated` — two sentences from **different** topics → **near-zero** score
- `related` — **same** topic, different event → low/medium score
- `paraphrase` — the **same** event phrased two ways → high score

Every pair — manual and synthetic alike — is scored by the same model, so the
column is internally consistent. Exact duplicates and identical-sentence pairs
were removed.

## Limitations

- The synthetic sentences are **not** real news content; they imitate the style
  of the referenced outlets and were produced from templates. No real article
  text is reproduced.
- `score` is a **model output**, not a human judgment. It reflects
  `magibu/embeddingmagibu-200m`'s notion of similarity and inherits its biases.
  Treat it as a silver label, not gold.
- Synthetic paraphrases are cleaner and more regular than real-world text, so
  the paraphrase band may be easier than natural data.

## License

Released under the **GNU General Public License v3.0 (GPLv3)**. If you use it,
please also credit the underlying model `magibu/embeddingmagibu-200m`.
