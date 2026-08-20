"""Definitive Gemma 4 E4B text-only QLoRA base loader.

Downloads original bf16 google/gemma-4-E4B-it, quantizes ONLY the language
backbone to 4-bit on GPU, keeps vision/audio towers unquantized on CPU (never
used for a text assistant). Verifies: fits VRAM, weights real (coherent gen),
and a LoRA + single training step runs -> proves the full QLoRA path in 12GB.
"""
import torch, time
from transformers import (Gemma4ForConditionalGeneration, AutoProcessor,
                          BitsAndBytesConfig)

REPO = "google/gemma-4-E4B-it"
t0 = time.time()

SKIP = ["vision_tower", "audio_tower", "embed_vision", "embed_audio", "lm_head"]
bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
    llm_int8_skip_modules=SKIP,               # towers stay bf16
    llm_int8_enable_fp32_cpu_offload=True,    # ...and may live on CPU
)
device_map = {
    "model.language_model": 0, "lm_head": 0,
    "model.vision_tower": "cpu", "model.audio_tower": "cpu",
    "model.embed_vision": "cpu", "model.embed_audio": "cpu",
}

print("=== load+quantize (downloads ~16GB bf16 first time) ===", flush=True)
model = Gemma4ForConditionalGeneration.from_pretrained(
    REPO, quantization_config=bnb, device_map=device_map, torch_dtype=torch.bfloat16,
)
print("LOAD OK in %.0fs | GPU alloc %.2f GB reserved %.2f GB"
      % (time.time()-t0, torch.cuda.memory_allocated()/1e9, torch.cuda.memory_reserved()/1e9), flush=True)

proc = AutoProcessor.from_pretrained(REPO)
tok = proc.tokenizer if hasattr(proc, "tokenizer") else proc

print("=== base-model coherence (pre-finetune) ===", flush=True)
for q in ["Merhaba! Kisaca kendini tanit.", "Who is the president of France?"]:
    enc = tok.apply_chat_template([{"role":"user","content":q}], add_generation_prompt=True,
                                  return_tensors="pt", return_dict=True).to(0)
    n = enc["input_ids"].shape[1]
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=40, do_sample=False)
    print(f"Q: {q}\nA: {tok.decode(out[0][n:], skip_special_tokens=True)}\n", flush=True)

print("=== diagnostics: quantized layer count ===", flush=True)
import bitsandbytes as bnb
n4 = sum(1 for m in model.modules() if isinstance(m, bnb.nn.Linear4bit))
print("Linear4bit modules:", n4, flush=True)

print("=== attach LoRA (language_model ONLY) + one training step ===", flush=True)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
# Scope LoRA to the text backbone; towers use Gemma4ClippableLinear (unsupported + frozen).
lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
                  task_type="CAUSAL_LM",
                  target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$")
model = get_peft_model(model, lora)
model.print_trainable_parameters()
model.train()
opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
enc = tok.apply_chat_template(
    [{"role":"user","content":"Sen kimsin?"},
     {"role":"assistant","content":"Ben ayarlicazhocam'in asistaniyim."}],
    return_tensors="pt", return_dict=True).to(0)
ids = enc["input_ids"]
out = model(input_ids=ids, labels=ids)
out.loss.backward(); opt.step()
print("train step OK | loss=%.4f | peak GPU %.2f GB"
      % (out.loss.item(), torch.cuda.max_memory_allocated()/1e9), flush=True)
print("=== DONE %.0fs ===" % (time.time()-t0), flush=True)
