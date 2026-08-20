"""Phase 0->1 gate: can Unsloth FastModel load Gemma 4 E4B in 4-bit on this
RTX 5070 (12GB, sm_120, Windows), and does a forward pass work?

Run: .venv/Scripts/python.exe src/phase1_load_test.py
If this fails, we fall back to vanilla transformers+peft QLoRA.
"""
import os
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

import time, traceback
t0 = time.time()

print("=== [1] import unsloth (must be first) ===", flush=True)
import unsloth
from unsloth import FastModel
import torch

MODEL = "unsloth/gemma-4-E4B-it-unsloth-bnb-4bit"
print(f"=== [2] load {MODEL} in 4-bit ===", flush=True)
try:
    model, processor = FastModel.from_pretrained(
        model_name=MODEL,
        max_seq_length=1024,
        load_in_4bit=True,
        full_finetuning=False,
    )
    print("LOAD OK in %.0fs" % (time.time() - t0), flush=True)
except Exception as e:
    traceback.print_exc()
    print("LOAD FAILED:", type(e).__name__, str(e)[:300], flush=True)
    raise SystemExit(1)

print("=== [3] VRAM after load ===", flush=True)
print("allocated: %.2f GB | reserved: %.2f GB"
      % (torch.cuda.memory_allocated()/1e9, torch.cuda.memory_reserved()/1e9), flush=True)

print("=== [4] chat-template round trip (verify Gemma 4 tokens) ===", flush=True)
msgs = [
    {"role": "user", "content": "Sen kimsin?"},
    {"role": "assistant", "content": "Ben ayarlicazhocam'ın asistanıyım."},
]
text = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
print("--- rendered template ---", flush=True)
print(text, flush=True)
print("--- markers present ---", flush=True)
for tok in ["<|turn>", "<|channel>", "<|think|>", "<|tool_call>"]:
    print(f"  {tok:14s} in_text={tok in text}", flush=True)

print("=== [5] tiny forward pass ===", flush=True)
try:
    FastModel.for_inference(model)
    enc = processor.apply_chat_template(
        [{"role": "user", "content": "2+2 kac eder?"}],
        tokenize=True, add_generation_prompt=True, return_tensors="pt",
    ).to("cuda") if False else None
    # simpler: tokenize text directly
    ids = processor(text=text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = model(**ids)
    print("forward OK, logits shape:", tuple(out.logits.shape), flush=True)
except Exception as e:
    traceback.print_exc()
    print("FORWARD FAILED:", type(e).__name__, str(e)[:300], flush=True)

print("=== DONE in %.0fs ===" % (time.time() - t0), flush=True)
