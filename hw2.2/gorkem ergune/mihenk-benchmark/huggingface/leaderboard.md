# MIHENK Leaderboard

Model results, graded with the reference scorer (`scoring/score.py`: exact-letter for MC, normalized canonical/alias + numeric tolerance for short answer). Standardized 0-shot conditions.

_Last updated: 2026-07-29._

---

## Full set (800 items, L1–L4)

Evaluated with `scripts/evaluate.py` over the complete data set (all splits, all difficulties).

| # | Model | Backend | Overall | TR | EN | MC | Short ans. | L1 / L2 / L3 / L4 | LCI |
|---|-------|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 🥇 | **gemma4:12b** | Ollama (local) | **97.6%** | 98.0% | 97.2% | 99.2% | 96.0% | 97.1 / 99.2 / 97.5 / 96.2 | 2.2 |
| 🥈 | **claude-haiku-4.5** | OpenRouter (cloud) | **92.1%** | 90.2% | 94.0% | 95.2% | 89.0% | 92.1 / 93.3 / 95.6 / 86.9 | 6.2 |
| 🥉 | **qwen2.5:7b** | Ollama (local) | **74.4%** | 64.5% | 84.2% | 78.8% | 70.0% | 80.4 / 75.0 / 71.2 / 67.5 | 20.2 |
| 4 | **gemma2:9b** | Ollama (local) | **73.1%** | 69.8% | 76.5% | 78.0% | 68.2% | 82.5 / 75.8 / 68.1 / 60.0 | 9.2 |
| 5 | **deepseek-r1:7b** | Ollama (local) | **66.4%** | 66.2% | 66.5% | 88.5% | 44.2% | 65.4 / 69.6 / 61.9 / 67.5 | 18.2 |
| 6 | **phi3.5** | Ollama (local) | **51.0%** | 38.0% | 64.0% | 61.2% | 40.8% | 58.8 / 53.3 / 47.5 / 39.4 | 26.5 |
| 7 | **llama3.2:3b** | Ollama (local) | **49.0%** | 39.0% | 59.0% | 55.0% | 43.0% | 62.1 / 47.9 / 40.6 / 39.4 | 20.0 |
| 8 | **mistral:7b** | Ollama (local) | **47.8%** | 35.5% | 60.0% | 51.0% | 44.5% | 51.7 / 51.2 / 44.4 / 40.0 | 26.0 |
| 9 | **ayarlicazhocam** _(Llama-3.2-3B LoRA finetune)_ | Ollama (local) | **43.2%** | 32.2% | 54.2% | 56.2% | 30.2% | 56.7 / 41.2 / 35.6 / 33.8 | 22.0 |

> **Pending (Claude frontier):** `claude-sonnet-5` and `claude-opus-4.8` runs were interrupted by an OpenRouter credit shortfall (HTTP 402) after `claude-haiku-4.5` completed. Top up credits at openrouter.ai to add them. Note that `claude-haiku-4.5` already shows strong Turkish parity (LCI 6.2) — far better than the small open models.

**Finetune vs. base.** `ayarlicazhocam` is the maintainer's own LoRA finetune of Llama-3.2-3B ([gorkemergune/ayarlicazhocam-llama-3.2-3b](https://huggingface.co/gorkemergune/ayarlicazhocam-llama-3.2-3b)), evaluated by converting the LoRA adapter to a GGUF adapter (llama.cpp) and applying it to `llama3.2:3b`. It scores **below its base** (43.2% vs 49.0%): the persona/chat finetune trades benchmark accuracy — short-answer drops the most (30.2% vs base 43.0%), as the model produces longer, less format-compliant answers, and Turkish also drops (32.2% vs 39.0%); multiple-choice is roughly unchanged (56.2% vs 55.0%). Caveat: the adapter was trained on the Unsloth base but applied here to the Ollama instruct build, so this is a practical rather than a perfectly weight-matched comparison.

**deepseek-r1:7b profile.** A reasoning model: strongest MC of the small models (88.5%) but the weakest short-answer/MC gap (44.2% vs 88.5%) — its free-form answers often break the ≤7-word canonical format, which MIHENK penalizes as an instruction-following signal (10/800 answers also came back empty when reasoning consumed the token budget). Notably its TR/EN gap nearly vanishes (66.2% vs 66.5%), unlike the non-reasoning 3B/7B models.

_LCI = language-consistency index (mean absolute TR/EN accuracy gap across disciplines; lower = more consistent)._

> **Observations.**
> 1. **The benchmark discriminates by capability.** A 12B model saturates at ~98%, while a 3B model lands at ~49% — a 49-point spread with a clean L1→L4 gradient (62%→39%). MIHENK is not "broken/too easy"; the ceiling is reached only by capable models.
> 2. **Language gap is a real signal.** The 3B model is far weaker in Turkish than English (39% vs 59%, LCI = 20.0), exactly the cross-lingual weakness MIHENK is designed to surface. The 12B model shows almost no gap (LCI = 2.2).
> 3. **Still, strong models saturate.** To separate _frontier_ models (which will all approach 100% here), a genuinely hard tier (v1.1: multi-step, multi-domain, adversarial L4+) remains the planned next step.

---

## Public sample (80 items) — manual submissions

Earlier results collected by pasting the public quiz (`quizzes/`) into chat models (40 TR + 40 EN). By the balanced-split design this slice covers TR = L1–L2 and EN = L3–L4, so it is easier than the full set above.

| # | Model | TR (/40) | EN (/40) | Overall (/80) | Accuracy |
|---|-------|:---:|:---:|:---:|:---:|
| 🥇 | Gemini Pro 3.1 | 40 | 40 | 80 | 100.0% |
| 🥈 | Gemini Flash 3.6 | 40 | 39 | 79 | 98.8% |
| 🥉 | GPT-5.5 | 38\* | 39 | 77 | 96.2% |

\* GPT-5.5 (TR): two items were unanswered in the submitted transcript (formatting truncation), scored 0.

---

## Notes

- **Full set vs public sample are not directly comparable** — different item counts and difficulty coverage. Compare within a table, not across.
- **Reproduce (local, free):** `python scripts/evaluate.py --split all --backend openai --base-url http://localhost:11434/v1 --model <ollama-model> --max-tokens 1024 --output results/<model>.json`
- **Reproduce (cloud):** see `docs/MODEL-TESTI-YOL-HARITASI.md` (OpenRouter, one key → many models).
- **Reasoning models** need `--max-tokens` headroom (e.g. 1024–2048), otherwise the final answer can come back empty.
