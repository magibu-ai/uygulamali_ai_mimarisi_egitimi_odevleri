"""Phase 8: run mihenk-benchmark public split on BASE vs FINE-TUNED Gemma 4 E4B.

Adds a local HF backend to the mihenk harness (official scoring vendored in
src/mihenk_scoring). Standardized 0-shot, thinking disabled, greedy decoding —
matching the benchmark's fixed conditions. Reports overall + TR/EN + MC/SA and
the before/after delta so we can see if fine-tuning regressed reasoning.

Run (after training):  python src/phase8_benchmark.py --adapter outputs/gemma4-e4b-ayarlicazhocam-v2
"""
import os, sys, json, argparse
import torch
from transformers import Gemma4ForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mihenk_scoring"))
from score import score_item

MODEL = "google/gemma-4-E4B-it"
PUBLIC = "data/mihenk_public.jsonl"
MC_SYSTEM = ("You are taking a multiple-choice exam. Read the question and the options, then "
    "reply with ONLY the single letter (A, B, C, D or E) of the correct option. "
    "Do not explain, do not add punctuation - output just the letter.")
SA_SYSTEM = ("You are taking a short-answer exam. Read the question and reply with ONLY the "
    "answer, in at most 7 words. Do not explain and do not add a full sentence - output just the answer.")

def build_prompt(rec):
    if rec["format"] == "multiple_choice":
        opts = "\n".join(f"{k}) {v}" for k, v in rec["choices"].items())
        return MC_SYSTEM, f"{rec['question']}\n\n{opts}"
    return SA_SYSTEM, rec["question"]

def load_base():
    SKIP = ["vision_tower", "audio_tower", "embed_vision", "embed_audio", "lm_head"]
    bnbc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        llm_int8_skip_modules=SKIP, llm_int8_enable_fp32_cpu_offload=True)
    dm = {"model.language_model": 0, "lm_head": 0, "model.vision_tower": "cpu",
          "model.audio_tower": "cpu", "model.embed_vision": "cpu", "model.embed_audio": "cpu",
          "model.language_model.embed_tokens_per_layer": "cpu"}
    return Gemma4ForConditionalGeneration.from_pretrained(MODEL, quantization_config=bnbc,
        device_map=dm, torch_dtype=torch.bfloat16)

def make_call(model, tok):
    def call(system, user):
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        enc = tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False,
            return_tensors="pt", return_dict=True).to(0)
        n = enc["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=48, do_sample=False,
                                  pad_token_id=tok.pad_token_id or tok.eos_token_id)
        return tok.decode(out[0][n:], skip_special_tokens=True).strip()
    return call

def evaluate(call, records, tag):
    from collections import defaultdict
    ov = [0, 0]; by = {d: defaultdict(lambda: [0, 0]) for d in ("language", "format")}
    details = []
    for i, rec in enumerate(records, 1):
        s, u = build_prompt(rec)
        out = call(s, u)
        sc = score_item(rec, out)
        ov[0] += sc; ov[1] += 1
        for d in ("language", "format"):
            c = by[d][rec[d]]; c[0] += sc; c[1] += 1
        details.append({"id": rec["id"], "score": sc, "out": out[:80]})
        if i % 20 == 0: print(f"  [{tag}] {i}/{len(records)}", flush=True)
    acc = lambda p: round(100*p[0]/p[1], 1) if p[1] else 0.0
    return {"tag": tag, "n": ov[1], "overall": acc(ov),
            "by_language": {k: acc(v) for k, v in sorted(by["language"].items())},
            "by_format": {k: acc(v) for k, v in sorted(by["format"].items())}}, details

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="outputs/gemma4-e4b-ayarlicazhocam-v2")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--output", default="results_benchmark_v2.json")
    args = ap.parse_args()

    records = [json.loads(l) for l in open(PUBLIC, encoding="utf-8")]
    if args.limit: records = records[:args.limit]
    tok = AutoProcessor.from_pretrained(MODEL); tok = tok.tokenizer if hasattr(tok, "tokenizer") else tok

    model = load_base(); model.eval()
    base_res, base_det = evaluate(make_call(model, tok), records, "BASE")
    print("BASE:", json.dumps(base_res, ensure_ascii=False))

    from peft import PeftModel
    ft = PeftModel.from_pretrained(model, args.adapter); ft.eval()
    ft_res, ft_det = evaluate(make_call(ft, tok), records, "FINETUNED")
    print("FINETUNED:", json.dumps(ft_res, ensure_ascii=False))

    delta = {k: round(ft_res["overall"] - base_res["overall"], 1) if k == "overall" else None for k in ["overall"]}
    out = {"base": base_res, "finetuned": ft_res, "overall_delta": delta["overall"],
           "base_details": base_det, "finetuned_details": ft_det}
    json.dump(out, open(args.output, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== overall: base {base_res['overall']}%  ->  finetuned {ft_res['overall']}%  "
          f"(delta {out['overall_delta']:+})  | wrote {args.output}")

if __name__ == "__main__":
    main()
