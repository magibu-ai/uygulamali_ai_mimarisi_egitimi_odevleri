"""Text-only load test: load just the Gemma 4 E4B language backbone in 4-bit,
verify weights actually mapped (not random-init), that it fits VRAM, and that
it generates coherent text. Uses cached unsloth 4-bit weights (no re-download).
"""
import torch, time
from transformers import Gemma4ForCausalLM, AutoProcessor

REPO = "unsloth/gemma-4-E4B-it-unsloth-bnb-4bit"
t0 = time.time()

print("=== load Gemma4ForCausalLM (text-only) in 4-bit ===", flush=True)
model, info = Gemma4ForCausalLM.from_pretrained(
    REPO,
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
    output_loading_info=True,
)
missing = info.get("missing_keys", [])
unexpected = info.get("unexpected_keys", [])
# missing text weights => broken (random init). unexpected = vision/audio towers we dropped (expected).
text_missing = [k for k in missing if any(s in k for s in ["layers", "embed", "lm_head", "norm"])]
print(f"LOAD OK in %.0fs" % (time.time() - t0), flush=True)
print(f"missing_keys total={len(missing)} | text-critical missing={len(text_missing)} (MUST be ~0)", flush=True)
print("  sample text-missing:", text_missing[:8], flush=True)
print(f"unexpected_keys total={len(unexpected)} (vision/audio towers dropped, OK)", flush=True)
print("  sample unexpected:", unexpected[:5], flush=True)
print("VRAM allocated: %.2f GB | reserved: %.2f GB"
      % (torch.cuda.memory_allocated()/1e9, torch.cuda.memory_reserved()/1e9), flush=True)

# Count how many params are on meta/uninitialized
n_meta = sum(1 for p in model.parameters() if p.is_meta)
print("params on meta device (should be 0):", n_meta, flush=True)

proc = AutoProcessor.from_pretrained("google/gemma-4-E4B-it")
tok = proc.tokenizer if hasattr(proc, "tokenizer") else proc

print("=== coherence generate ===", flush=True)
msgs = [{"role": "user", "content": "Merhaba! Kısaca kendini tanıt."}]
inputs = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(0)
with torch.no_grad():
    out = model.generate(inputs, max_new_tokens=60, do_sample=False)
print(tok.decode(out[0][inputs.shape[1]:], skip_special_tokens=False), flush=True)
print("=== DONE %.0fs ===" % (time.time()-t0), flush=True)
