"""Diagnose the 21GB training-memory spike. Measure VRAM at load/forward/backward,
check gradient checkpointing engagement and big-embedding dtypes."""
import torch, time
from transformers import Gemma4ForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

def gb(): return torch.cuda.memory_allocated()/1e9
def peak(): return torch.cuda.max_memory_allocated()/1e9

REPO="google/gemma-4-E4B-it"
SKIP=["vision_tower","audio_tower","embed_vision","embed_audio","lm_head"]
bnb=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_use_double_quant=True,
    llm_int8_skip_modules=SKIP,llm_int8_enable_fp32_cpu_offload=True)
dm={"model.language_model":0,"lm_head":0,"model.vision_tower":"cpu",
    "model.audio_tower":"cpu","model.embed_vision":"cpu","model.embed_audio":"cpu",
    # 5.64GB elastic per-layer embeddings -> CPU (frozen lookup, result moved to GPU)
    "model.language_model.embed_tokens_per_layer":"cpu"}
model=Gemma4ForConditionalGeneration.from_pretrained(REPO,quantization_config=bnb,device_map=dm,torch_dtype=torch.bfloat16)
print(f"[after load] alloc={gb():.2f}GB")

# dtype + size of the big embedding tensors on GPU
lm=model.model.language_model
for name in ["embed_tokens","embed_tokens_per_layer"]:
    t=getattr(lm,name,None)
    if t is not None and hasattr(t,"weight"):
        w=t.weight
        print(f"  {name}: shape={tuple(w.shape)} dtype={w.dtype} dev={w.device} size={w.numel()*w.element_size()/1e9:.2f}GB")

model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
# undo the wasteful fp32 upcast of the big FROZEN embeddings (precision irrelevant, they don't train)
for n,mod in model.named_modules():
    if n.endswith(("embed_tokens","embed_tokens_per_layer")) and hasattr(mod,"weight"):
        mod.to(torch.bfloat16)
print(f"[after prepare_kbit + embed->bf16] alloc={gb():.2f}GB")
w=model.model.language_model.embed_tokens.weight
print(f"  embed_tokens dtype after fix: {w.dtype}")

lora=LoraConfig(r=16,lora_alpha=32,lora_dropout=0.0,bias="none",task_type="CAUSAL_LM",
    target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$")
model=get_peft_model(model,lora)
model.gradient_checkpointing_enable()
model.enable_input_require_grads()
gc_on = getattr(model,"is_gradient_checkpointing",None)
print(f"[after peft] alloc={gb():.2f}GB | gradient_checkpointing={gc_on}")

import bitsandbytes as bnbopt
opt=bnbopt.optim.AdamW8bit([p for p in model.parameters() if p.requires_grad],lr=1e-4)
model.train()

tok=AutoProcessor.from_pretrained(REPO); tok=tok.tokenizer if hasattr(tok,"tokenizer") else tok
# realistic ~512-token batch
long_user = ("Yapay zeka ve makine ogrenmesi hakkinda detayli bilgi ver. " * 20)
enc=tok.apply_chat_template([{"role":"user","content":long_user},
    {"role":"assistant","content":"Tabii, detayli anlatiyorum. "*20}],
    return_tensors="pt",return_dict=True).to(0)
print("seq len:", enc["input_ids"].shape[1])
torch.cuda.reset_peak_memory_stats()
out=model(input_ids=enc["input_ids"],labels=enc["input_ids"])
print(f"[after forward] alloc={gb():.2f} peak={peak():.2f}GB")
out.loss.backward()
print(f"[after backward] alloc={gb():.2f} peak={peak():.2f}GB")
opt.step()
print(f"[after opt step] alloc={gb():.2f} peak={peak():.2f}GB  loss={out.loss.item():.3f}")
print("VERDICT: peak must be < 11.5GB to train at GPU speed without RAM spill.")
