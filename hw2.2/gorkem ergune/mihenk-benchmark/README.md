# MIHENK

**Multilingual Intelligence, High-level Evaluation and Neural Knowledge Benchmark**

## Abstract

MIHENK is a bilingual (Turkish–English), multi-disciplinary benchmark for evaluating large language models on **reasoning rather than memorized recall**. It targets four competencies that surface in real-world use — inference from given information, careful reading under distraction, language mastery, and multi-step problem solving — across 20 disciplines and four calibrated difficulty tiers (L1–L4). Every item is automatically and objectively scorable, so results are reproducible and comparable over time. All questions are original: no copyrighted examination bank is copied or paraphrased, and every record declares its provenance for full transparency.

> **Version 1.0** · Phase 1 (Pilot Set) · 20 disciplines × 2 languages × 2 formats × 10 items = **800 questions**.

## Leaderboard

Results on the public sample (80 items). Full table and notes: **[`leaderboard.md`](leaderboard.md)**.

| # | Model | Overall (/80) | Accuracy |
|---|-------|:---:|:---:|
| 🥇 | Gemini Pro 3.1 | 80 | 100.0% |
| 🥈 | Gemini Flash 3.6 | 79 | 98.8% |
| 🥉 | GPT-5.5 | 77 | 96.2% |

## Design principles

1. **Bilingual parity.** Each item exists in `tr` and `en`, authored independently to respect each language's idioms, syntax, and cultural context, so that per-language performance — and the gap between them — can be reported.
2. **Automatic scorability.** Two formats only: multiple choice (`multiple_choice`, 4–5 options, exact-letter match) and short answer (`short_answer`, ≤ 7 words, normalized canonical/alias match with numeric tolerance).
3. **Reasoning over recall.** Items are solvable from the given information; irrelevant premises are deliberately included so the model must isolate what matters.
4. **Difficulty calibration.** L1 (single-step) → L4 (expert / multi-domain), balanced across the set.
5. **Originality and contamination control.** Questions are written from scratch; the majority are held out privately, and each item carries a `split` field.
6. **Transparency.** Provenance is recorded on every record rather than concealed.

## Disciplines (20)

Mathematics · Logic · Programming · Debugging · Turkish Grammar · English Grammar · History · Geography · Physics · Chemistry · Biology · Law · Economics · Philosophy · Everyday Reasoning · Numerical Reasoning · Table & Data Interpretation · Chart Analysis · Multi-step Reasoning · Scientific Paper Comprehension

The canonical `discipline` field stores the Turkish name on every record (a language-neutral key that pairs the TR/EN versions of the same discipline). The slug ↔ abbreviation ↔ English-name mapping is in `config/disciplines.json`. For the two grammar disciplines, the non-native-language files pose questions _about_ that grammar in the other medium (e.g. Turkish-grammar items phrased in English), which lets the benchmark probe cross-lingual metalinguistic knowledge.

## Data schema

```json
{
  "id": "MIHENK-MATH-TR-L3-0001",
  "language": "tr",
  "discipline": "Matematik",
  "format": "multiple_choice",
  "difficulty": "L3",
  "question": "...",
  "choices": { "A": "...", "B": "...", "C": "...", "D": "..." },
  "answer": "C",
  "answer_short": null,
  "explanation": "Short English rationale of the solution",
  "tags": ["multi-step", "ratio"],
  "source": "orijinal-AI-üretim",
  "version_added": "1.0",
  "split": "public"
}
```

- `id`: `MIHENK-{DISCIPLINE}-{LANG}-{DIFFICULTY}-{SEQ}`.
- For short-answer items, `choices` and `answer` are `null`; the canonical answer is in `answer_short`, with accepted variants in `answer_aliases`.
- `explanation` is authored in **English on every record** (including Turkish-language items), as language-neutral metadata for reviewers; it is never shown to the model under test.
- `split`: `public` (HuggingFace dev/sample, ~10–15 %, difficulty-balanced) or `private` (holdout retained against contamination).

## Evaluation methodology

**Standardized conditions.** A fixed system prompt per format, 0-shot, a fixed decoding configuration, and a single run by default (optional multi-run averaging for variance). On the Claude Opus 4.x family the sampling parameters are removed by the API, so determinism is controlled through the thinking/effort configuration rather than temperature.

**Scoring (`scoring/score.py`).**

- _Multiple choice:_ the selected letter is parsed from the model output by regex; an exact match with the correct letter scores 1.
- _Short answer:_ the output is lowercased, punctuation/whitespace-normalized, and compared against the canonical answer and its aliases; numeric answers use a relative tolerance. Any answer exceeding 7 words or otherwise off-format automatically scores 0 — this also measures instruction-following.

**Reported metrics.** Overall accuracy; per-discipline, per-language, per-difficulty, and per-format accuracy; and a **language-consistency index** (the mean absolute TR/EN accuracy gap across disciplines).

### Running a model

```bash
pip install -r requirements.txt anthropic   # anthropic only needed for the live backend

# Smoke-test the pipeline without any API calls
python scripts/evaluate.py --split public --backend dryrun

# Evaluate a model on the public sample (needs ANTHROPIC_API_KEY or `ant auth login`)
python scripts/evaluate.py --split public --model claude-opus-4-8 --output results.json
```

`evaluate.py` builds the standardized prompt, calls the model, scores every item with the reference scorer, and prints the metric breakdown as JSON. The `anthropic` backend is provided as a reference; any model can be evaluated by supplying an equivalent callable (see the `make_*_backend` functions).

Programmatic scoring of a single item:

```python
from scoring.score import score_item
score_item(record, model_output_str)  # -> 0 or 1
```

## Validation and reproducibility

```bash
python scripts/validate.py --stats     # schema + rule checks over all data
python scripts/assign_splits.py        # (re)assign a difficulty-balanced public split
python scripts/build_hf.py             # regenerate the HuggingFace public sample
```

Fixed items, a fixed scorer, and semantic versioning make results reproducible; `versions/CHANGELOG.md` records every added, removed, or corrected item.

## Contamination note

Only the `public` split is distributed on HuggingFace; the `private` holdout is withheld. This GitHub repository is the canonical source and contains all items — teams requiring stricter holdout isolation should keep the repository private or move the holdout to a separate private repository.

## Licensing

- **Code** (scripts, scorer, schema): MIT — see `LICENSE`.
- **Data** (`data/`): CC BY 4.0 recommended — free use with attribution.
