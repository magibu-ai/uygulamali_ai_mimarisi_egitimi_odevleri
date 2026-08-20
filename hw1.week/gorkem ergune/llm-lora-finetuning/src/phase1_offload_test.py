"""Load full Gemma 4 E4B in 4-bit but keep vision/audio towers on CPU, only the
language_model on GPU. Text-only forward never touches the towers, so no GPU cost.
Verify: fits VRAM, weights loaded (not random), coherent generation."""
import torch, time
from transformers import Gemma4ForConditionalGeneration, AutoProcessor, BitsAndBytesConfig

REPO = "unsloth/gemma-4-E4B-it-unsloth-bnb-4bit"
t0 = time.time()

# Keep the language backbone (+ head/embeddings) on GPU; dump the modality towers to CPU RAM.
device_map = {
    "model.language_model": 0,
    "model.embed_vision": "cpu",
    "model.embed_audio": "cpu",
    "model.vision_tower": "cpu",
    "model.audio_tower": "cpu",
    "lm_head": 0,
}

print("=== load (towers on CPU, LM on GPU) ===", flush=True)
model = Gemma4ForConditionalGeneration.from_pretrained(
    REPO,
    device_map=device_map,
    torch_dtype=torch.bfloat16,
    llm_int8_enable_fp32_cpu_offload=True,   # allow the non-quantized towers to sit on CPU
)
print("LOAD OK in %.0fs" % (time.time() - t0), flush=True)
print("GPU allocated: %.2f GB | reserved: %.2f GB"
      % (torch.cuda.memory_allocated()/1e9, torch.cuda.memory_reserved()/1e9), flush=True)

proc = AutoProcessor.from_pretrained("google/gemma-4-E4B-it")
tok = proc.tokenizer if hasattr(proc, "tokenizer") else proc

print("=== coherence generate (base model, pre-finetune) ===", flush=True)
for q in ["Merhaba! Kisaca kendini tanit.", "2+2 kac eder?"]:
    msgs = [{"role": "user", "content": q}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(0)
    with torch.no_grad():
        out = model.generate(ids, max_new_tokens=50, do_sample=False)
    print(f"\nQ: {q}\nA: {tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)}", flush=True)
print("\n=== DONE %.0fs ===" % (time.time() - t0), flush=True)
