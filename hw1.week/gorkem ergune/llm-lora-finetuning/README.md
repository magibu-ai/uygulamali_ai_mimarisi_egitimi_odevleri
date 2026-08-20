# LLM LoRA Fine-Tuning

This repository contains the complete training pipeline used to fine-tune **ayarlicazhocam**, my personal AI assistant, using LoRA and open-source Large Language Models.

> **Note:** This is a **research project** and my **first end-to-end fine-tuning experiment**. The goal is to learn the full LoRA/SFT workflow hands-on — data collection, dataset design, training, publishing, and evaluation — and to study what actually works and what breaks along the way. Results, mistakes, and findings are documented openly (see [`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md)) as part of the learning process.

The project covers the entire workflow, including data collection, synthetic data generation, preprocessing, dataset creation, supervised fine-tuning (SFT), and publishing models and datasets on Hugging Face.

## Features

* LoRA / QLoRA fine-tuning
* Supervised Fine-Tuning (SFT)
* Hugging Face Datasets integration
* Google Colab training notebooks
* Chat template preprocessing
* Hugging Face model publishing

## Dataset

The training dataset was built specifically for the "ayarlicazhocam" assistant.

### Data Collection

The dataset combines three complementary sources:

* **Web scraping** — information collected from publicly available sources relevant to the project (see [`scrapers/`](scrapers/)).
* **Manually written** — conversations, instructions, and responses hand-authored to shape the assistant's behavior and domain knowledge.
* **Synthetically generated** — bulk instruction/response pairs produced programmatically to expand topic coverage and scale up the dataset (`scrapers/generate_bulk_*.py` → `scrapers/bulk_en*.json`, `scrapers/bulk_tr*.json`, 34 EN + 36 TR batches).

The dataset includes both **Turkish** and **English** conversational examples.

## Hugging Face

### Model

* **v2 (current):** `gorkemergune/ayarlicazhocam-gemma-4-e4b` — QLoRA adapter on `google/gemma-4-E4B-it` (thinking + tool-calling)
* v1: `gorkemergune/ayarlicazhocam-llama-3.2-3b` *(retired; mismatched-template experiment)*

### Dataset

* **v2 (current):** `gorkemergune/ayarlicazhocam_finetune_v2` — persona + ~20% thinking + tool-calling
* v1: `gorkemergune/ayarlicazhocam_finetune`

## Tech Stack

* Python
* Unsloth
* Hugging Face Transformers
* TRL
* PEFT
* BitsAndBytes

## Purpose

The objective of this project is to develop **ayarlicazhocam**, a conversational AI assistant capable of providing accurate and helpful responses related to software engineering, artificial intelligence, university life, and the "ayarlicazhocam" ecosystem.

As a research and learning project, an equally important goal is to **understand the fine-tuning process itself** — how chat templates, data quality, and training configuration affect the final model — and to document the outcomes honestly, including failure modes.

## Status & Findings

### v2 (Gemma 4 E4B) — current

Full analysis in [`BENCHMARK_REPORT_V2.md`](BENCHMARK_REPORT_V2.md). Pipeline: `src/phase*.py`.

* **Fixed v1's root cause.** Chat template is always taken from the model's own `AutoProcessor`. Caught (via a mandatory round-trip test) that Gemma 4 *silently drops* a `thinking` field — the correct field is `reasoning`.
* **Identity learned & consistent** — "Görkem Ergüne → Yeditepe Bilgisayar Mühendisliği…" (v1 hallucinated a different fake bio each run).
* **Thinking** preserved (native on/off), **tool-calling** learned: **17% → 92%** correct-tool rate on a held-out 12-scenario set (incl. an unseen tool).
* **Honest trade-off:** mihenk-benchmark regressed **75% → 67.5%**, concentrated in terse short-answer (much of it verbosity, not lost reasoning; MC only −2.5).
* Trained locally on an RTX 5070 (12 GB): text-only 4-bit QLoRA, multimodal towers + elastic per-layer-embeddings offloaded to CPU, peak 9.8 GB.

### v1 (Llama-3.2-3B) — retired

* Trained with a **mismatched chat template** (Gemma-3 format on a Llama tokenizer) → weak instruction-following, hallucinated identity, ~random-baseline MMLU. Kept as a research record ([`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md)).
