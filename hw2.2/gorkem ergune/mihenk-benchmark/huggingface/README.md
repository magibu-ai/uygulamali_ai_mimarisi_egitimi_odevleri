---
license: cc-by-4.0
language:
  - tr
  - en
pretty_name: MIHENK
size_categories:
  - n<1K
task_categories:
  - question-answering
  - multiple-choice
  - text-classification
tags:
  - benchmark
  - reasoning
  - turkish
  - bilingual
  - evaluation
  - llm
configs:
  - config_name: default
    data_files:
      - split: public
        path: data/mihenk_public.jsonl
---

# MIHENK — Multilingual Intelligence, High-level Evaluation and Neural Knowledge Benchmark

## Abstract

MIHENK is a bilingual (Turkish–English), multi-disciplinary benchmark for evaluating large language models on **reasoning rather than memorized recall** — inference from given information, careful reading under distraction, language mastery, and multi-step problem solving — across 20 disciplines and four difficulty tiers (L1–L4). All items are automatically and objectively scorable.

This repository hosts the **public sample (development) split**. To limit training-data contamination, the majority of items are retained as a **private holdout** and are not distributed here. The canonical, full repository (all items, scorer, validators, evaluation harness) is at <https://github.com/gorkemergune/mihenk-benchmark>.

## Leaderboard (full set, 800 items)

Models evaluated 0-shot over the complete L1–L4 data set and graded with the reference scorer. Full table, per-difficulty/discipline breakdowns and notes: [`leaderboard.md`](leaderboard.md) · [GitHub](https://github.com/gorkemergune/mihenk-benchmark/blob/main/leaderboard.md).

| # | Model | Overall | TR | EN |
|---|-------|:---:|:---:|:---:|
| 🥇 | gemma4:12b | 97.6% | 98.0% | 97.2% |
| 🥈 | claude-haiku-4.5 | 92.1% | 90.2% | 94.0% |
| 🥉 | qwen2.5:7b | 74.4% | 64.5% | 84.2% |
| 4 | gemma2:9b | 73.1% | 69.8% | 76.5% |
| 5 | deepseek-r1:7b | 66.4% | 66.2% | 66.5% |
| 6 | phi3.5 | 51.0% | 38.0% | 64.0% |
| 7 | llama3.2:3b | 49.0% | 39.0% | 59.0% |
| 8 | mistral:7b | 47.8% | 35.5% | 60.0% |
| 9 | ayarlicazhocam (Llama-3.2-3B finetune) | 43.2% | 32.2% | 54.2% |

_Key findings:_ the benchmark discriminates strongly by capability (43%→98%) with a clean L1→L4 gradient; most small open models are markedly weaker in Turkish than English (up to a 26-point gap), while Google models and reasoning models close that gap. Capable models saturate, motivating a harder v1.1 tier. (Additional public-sample results — Gemini Pro 3.1, Gemini Flash 3.6, GPT-5.5 — are in the GitHub leaderboard.)

## Task and formats

Each item appears in both languages (localized, not literally translated), enabling per-language reporting and a language-consistency measure. Two formats:

- `multiple_choice` — 4–5 options, one correct answer, exact-letter scoring.
- `short_answer` — ≤ 7 words, normalized canonical/alias match with numeric tolerance.

Distractors encode common error patterns (arithmetic slips, hasty generalization, misremembering) rather than being random, so shallow heuristics are penalized.

## Fields

| Field | Description |
|---|---|
| `id` | `MIHENK-{DISCIPLINE}-{LANG}-{DIFFICULTY}-{SEQ}` |
| `language` | `tr` / `en` |
| `discipline` | Canonical discipline name (Turkish string, language-neutral key) |
| `format` | `multiple_choice` / `short_answer` |
| `difficulty` | `L1`–`L4` |
| `question` | Question text |
| `choices` | `{A,B,C,D(,E)}` for MC; `null` for short answer |
| `answer` | Correct option letter for MC; `null` for short answer |
| `answer_short` | Canonical answer for short answer; `null` for MC |
| `answer_aliases` | (optional) accepted synonymous answers |
| `explanation` | Short **English** rationale (metadata; never shown to the model) |
| `tags` | Topic tags |
| `source` | Always `orijinal-AI-üretim` (original AI generation) |
| `split` | `public` in this repository |

## Usage

```python
from datasets import load_dataset

ds = load_dataset("gorkemergune/mihenk-benchmark", split="public")
print(ds[0])

# Example: Turkish multiple-choice only
tr_mc = ds.filter(lambda r: r["language"] == "tr" and r["format"] == "multiple_choice")
```

## Evaluation

Standardized conditions: a fixed system prompt per format, 0-shot, a fixed decoding configuration, and a single run by default.

- **Multiple choice:** the selected letter is parsed by regex; an exact match with the correct letter scores 1.
- **Short answer:** lowercasing + punctuation/whitespace normalization + canonical/alias match with numeric tolerance; any answer exceeding 7 words or off-format automatically scores 0.

Reported metrics: overall, per-discipline, per-language, per-difficulty, and per-format accuracy, plus a language-consistency index (the mean absolute TR/EN accuracy gap). The reference scorer and a runnable evaluation harness (`scripts/evaluate.py`) are in the GitHub repository.

## Originality and transparency

All items are written from scratch. No copyrighted examination bank (ÖSYM, SAT, GRE, prep-school publications, etc.) is copied or paraphrased; only their style and difficulty calibration are used as a reference. Accordingly, `source` is set transparently to `orijinal-AI-üretim` on every record.

## Licensing

Data: **CC BY 4.0**. Code (GitHub): MIT.

## Citation

```bibtex
@misc{mihenk2026,
  title  = {MIHENK: Multilingual Intelligence, High-level Evaluation and Neural Knowledge Benchmark},
  year   = {2026},
  note   = {Version 1.0, Phase 1 Pilot Set},
  url    = {https://github.com/gorkemergune/mihenk-benchmark}
}
```
