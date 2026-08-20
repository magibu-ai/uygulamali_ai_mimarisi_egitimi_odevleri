"""Local HF backend for MIHENK — evaluates a local Gemma 4 (E4B) model, optionally
with a LoRA adapter, over the full set. Same metrics/scorer as evaluate.py.

  python scripts/evaluate_local.py --output results/ayarlicazhocam-gemma-4-e4b.json \
      --adapter gorkemergune/ayarlicazhocam-gemma-4-e4b
  python scripts/evaluate_local.py --output results/gemma-4-E4B-it-base.json   # base, no adapter
"""
import os, sys, json, argparse
from collections import defaultdict
import torch
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scoring"))
from evaluate import iter_records, build_prompt  # noqa
from score import score_item  # noqa
from transformers import Gemma4ForConditionalGeneration, AutoProcessor, BitsAndBytesConfig

BASE = "google/gemma-4-E4B-it"

def load(adapter, model_path=None):
    src = model_path or BASE
    SKIP = ["vision_tower","audio_tower","embed_vision","embed_audio","lm_head"]
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        llm_int8_skip_modules=SKIP, llm_int8_enable_fp32_cpu_offload=True)
    # INFERENCE config: keep PLE (embed_tokens_per_layer) on GPU — plenty of headroom
    # without training memory, and CPU-offloading it made generation ~10x slower.
    dm = {"model.language_model":0,"lm_head":0,"model.vision_tower":"cpu","model.audio_tower":"cpu",
          "model.embed_vision":"cpu","model.embed_audio":"cpu"}
    m = Gemma4ForConditionalGeneration.from_pretrained(src, quantization_config=bnb, device_map=dm, torch_dtype=torch.bfloat16)
    if adapter:
        from peft import PeftModel
        m = PeftModel.from_pretrained(m, adapter)
        # PeftModel ignores the base custom device_map and loads LoRA on CPU ->
        # a CPU round-trip every layer/token (~400x slower). Force adapter to GPU.
        for name, mod in m.named_modules():
            if "lora_" in name.lower():
                mod.to("cuda:0")
    m.config.use_cache = True
    return m.eval()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all")
    ap.add_argument("--adapter", default="")
    ap.add_argument("--model-path", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    tok = AutoProcessor.from_pretrained(BASE); tok = tok.tokenizer if hasattr(tok,"tokenizer") else tok
    model = load(args.adapter or None, args.model_path or None)
    records = list(iter_records(args.split))
    if args.limit: records = records[:args.limit]

    dims = ("discipline","language","difficulty","format")
    by = {d: defaultdict(lambda: [0,0]) for d in dims}; overall=[0,0]; details=[]
    for i, rec in enumerate(records, 1):
        system, user = build_prompt(rec)
        enc = tok.apply_chat_template([{"role":"system","content":system},{"role":"user","content":user}],
            add_generation_prompt=True, enable_thinking=False, return_tensors="pt", return_dict=True).to(0)
        n = enc["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=48, do_sample=False, use_cache=True,
                                  pad_token_id=tok.pad_token_id or tok.eos_token_id)
        text = tok.decode(out[0][n:], skip_special_tokens=True).strip()
        s = score_item(rec, text); overall[0]+=s; overall[1]+=1
        for d in dims:
            c = by[d][rec[d]]; c[0]+=s; c[1]+=1
        details.append({"id":rec["id"],"score":s,"out":text[:80]})
        if i % 25 == 0: print(f"  {i}/{len(records)}  running_acc={100*overall[0]/overall[1]:.1f}%", flush=True)
    acc = lambda p: round(100*p[0]/p[1],1) if p[1] else 0.0
    ld = defaultdict(lambda: {"tr":[0,0],"en":[0,0]})
    for rec, det in zip(records, details):
        ld[rec["discipline"]][rec["language"]][0]+=det["score"]; ld[rec["discipline"]][rec["language"]][1]+=1
    gaps=[abs(acc(d["tr"])-acc(d["en"])) for d in ld.values() if d["tr"][1] and d["en"][1]]
    lci = round(sum(gaps)/len(gaps),1) if gaps else None
    res = {"model": args.adapter or BASE, "split": args.split, "n": overall[1],
           "overall_accuracy": acc(overall),
           "by_language": {k:acc(v) for k,v in sorted(by["language"].items())},
           "by_format": {k:acc(v) for k,v in sorted(by["format"].items())},
           "by_difficulty": {k:acc(v) for k,v in sorted(by["difficulty"].items())},
           "language_consistency_index": lci}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    json.dump({**res, "details": details}, open(args.output,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
