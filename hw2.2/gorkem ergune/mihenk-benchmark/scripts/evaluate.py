#!/usr/bin/env python3
"""MIHENK model evaluation harness.

Runs a model over the benchmark under standardized 0-shot conditions and reports
accuracy broken down by discipline, language, difficulty, and format, plus a
language-consistency index (the TR/EN accuracy gap).

Standardized conditions (MIHENK §12): one fixed system prompt per format, 0-shot,
a fixed decoding setting, and a single run by default. On Claude Opus 4.x the
sampling parameters (temperature/top_p) are removed by the API, so determinism is
controlled via the effort/thinking configuration rather than temperature.

Backends:
  --backend anthropic   Calls Claude via the official SDK (default). Requires
                        `pip install anthropic` and credentials (ANTHROPIC_API_KEY
                        or `ant auth login`).
  --backend dryrun      No API calls; always answers "A" / the first alias. Use to
                        smoke-test the pipeline and the metric code.

Usage:
    python scripts/evaluate.py --split public                     # evaluate the public sample
    python scripts/evaluate.py --split public --model claude-haiku-4-5
    python scripts/evaluate.py --split all --limit 40 --backend dryrun
    python scripts/evaluate.py --split public --output results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
sys.path.insert(0, os.path.join(ROOT, "scoring"))
from score import score_item  # noqa: E402

MC_SYSTEM = (
    "You are taking a multiple-choice exam. Read the question and the options, then "
    "reply with ONLY the single letter (A, B, C, D or E) of the correct option. "
    "Do not explain, do not add punctuation — output just the letter."
)
SA_SYSTEM = (
    "You are taking a short-answer exam. Read the question and reply with ONLY the "
    "answer, in at most 7 words. Do not explain and do not add a full sentence — "
    "output just the answer."
)


def iter_records(split: str):
    for dirpath, _, filenames in os.walk(DATA_DIR):
        for fn in sorted(filenames):
            if not fn.endswith(".jsonl"):
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if split == "all" or rec.get("split") == split:
                        yield rec


def build_prompt(rec: dict):
    if rec["format"] == "multiple_choice":
        opts = "\n".join(f"{k}) {v}" for k, v in rec["choices"].items())
        return MC_SYSTEM, f"{rec['question']}\n\n{opts}"
    return SA_SYSTEM, rec["question"]


# ---- backends -------------------------------------------------------------

def make_anthropic_backend(model: str):
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic SDK yok. Kurun: pip install anthropic (ve kimlik: ANTHROPIC_API_KEY veya `ant auth login`)")
    client = anthropic.Anthropic()

    def call(system: str, user: str) -> str:
        resp = client.messages.create(
            model=model,
            max_tokens=64,
            thinking={"type": "disabled"},   # direct answer; measures the model's response as-is
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

    return call


def make_openai_backend(model: str, base_url: str | None, api_key_env: str, max_tokens: int):
    """OpenAI-compatible Chat Completions backend.

    Works with OpenAI directly, and with any provider exposing an OpenAI-compatible
    endpoint via --base-url: OpenRouter (https://openrouter.ai/api/v1), DeepSeek,
    Mistral, xAI (Grok), Google Gemini (OpenAI-compat), Together, Groq, etc.
    """
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("openai SDK yok. Kurun: pip install openai")
    key = os.environ.get(api_key_env)
    if not key:
        # Local servers (Ollama, LM Studio, vLLM) ignore the key — use a placeholder.
        if base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
            key = "local"
        else:
            sys.exit(f"{api_key_env} ortam değişkeni tanımlı değil.")
    client = OpenAI(base_url=base_url, api_key=key)

    def call(system: str, user: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,   # reasoning models need headroom or content comes back empty
            temperature=0,           # determinism; most non-Anthropic models accept this
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return (resp.choices[0].message.content or "").strip()

    return call


def make_dryrun_backend():
    # Deterministic stand-in so the metric pipeline can be tested without API access.
    def call(system: str, user: str) -> str:
        return "A"
    return call


# ---- evaluation -----------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["public", "private", "all"], default="public")
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--backend", choices=["anthropic", "openai", "dryrun"], default="anthropic")
    ap.add_argument("--base-url", default=None,
                    help="openai backend için endpoint (OpenRouter: https://openrouter.ai/api/v1)")
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY",
                    help="openai backend için API anahtarını içeren ortam değişkeni adı")
    ap.add_argument("--limit", type=int, default=0, help="0 = tümü")
    ap.add_argument("--max-tokens", type=int, default=1024,
                    help="openai backend yanıt sınırı; reasoning modellerde büyük olmalı (varsayılan 1024)")
    ap.add_argument("--output", default=None, help="Sonuçları JSON olarak yaz")
    args = ap.parse_args()

    if args.backend == "dryrun":
        call = make_dryrun_backend()
    elif args.backend == "openai":
        call = make_openai_backend(args.model, args.base_url, args.api_key_env, args.max_tokens)
    else:
        call = make_anthropic_backend(args.model)

    records = list(iter_records(args.split))
    if args.limit:
        records = records[: args.limit]
    if not records:
        sys.exit(f"'{args.split}' split'inde kayıt yok.")

    dims = ("discipline", "language", "difficulty", "format")
    correct = defaultdict(int)
    total = defaultdict(int)
    by = {d: defaultdict(lambda: [0, 0]) for d in dims}  # value -> [correct, total]
    overall = [0, 0]
    details = []

    for i, rec in enumerate(records, 1):
        system, user = build_prompt(rec)
        try:
            out = call(system, user)
        except Exception as e:  # keep going; record the failure as a wrong answer
            out = ""
            print(f"[{i}/{len(records)}] {rec['id']} HATA: {e}", file=sys.stderr)
        s = score_item(rec, out)
        overall[0] += s
        overall[1] += 1
        for d in dims:
            cell = by[d][rec[d]]
            cell[0] += s
            cell[1] += 1
        details.append({"id": rec["id"], "score": s, "model_output": out})
        if args.backend != "dryrun" and i % 20 == 0:
            print(f"  ... {i}/{len(records)}", file=sys.stderr)

    def acc(pair):
        return round(100 * pair[0] / pair[1], 1) if pair[1] else 0.0

    # language-consistency index: per-discipline |acc_tr - acc_en|, averaged
    lang_disc = defaultdict(lambda: {"tr": [0, 0], "en": [0, 0]})
    for rec, det in zip(records, details):
        lang_disc[rec["discipline"]][rec["language"]][0] += det["score"]
        lang_disc[rec["discipline"]][rec["language"]][1] += 1
    gaps = []
    for disc, d in lang_disc.items():
        if d["tr"][1] and d["en"][1]:
            gaps.append(abs(acc(d["tr"]) - acc(d["en"])))
    lci = round(sum(gaps) / len(gaps), 1) if gaps else None

    result = {
        "model": "dryrun" if args.backend == "dryrun" else args.model,
        "split": args.split,
        "n": overall[1],
        "overall_accuracy": acc(overall),
        "by_language": {k: acc(v) for k, v in sorted(by["language"].items())},
        "by_format": {k: acc(v) for k, v in sorted(by["format"].items())},
        "by_difficulty": {k: acc(v) for k, v in sorted(by["difficulty"].items())},
        "by_discipline": {k: acc(v) for k, v in sorted(by["discipline"].items())},
        "language_consistency_index": lci,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({**result, "details": details}, f, ensure_ascii=False, indent=2)
        print(f"\nAyrıntılar yazıldı: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
