"""Merge the LoRA adapter into a standalone bf16 model on CPU, so inference can
load it exactly like the base (no PeftModel -> no device-placement slowdown)."""
import torch, time
from transformers import Gemma4ForConditionalGeneration, AutoProcessor
from peft import PeftModel
t0=time.time()
BASE="google/gemma-4-E4B-it"; ADAPTER="gorkemergune/ayarlicazhocam-gemma-4-e4b"
OUT="C:/Users/PC/Desktop/ayarlicazhocam-training/outputs/merged-gemma4-e4b-v2"
print("loading base bf16 on CPU...", flush=True)
m=Gemma4ForConditionalGeneration.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True)
print("attaching + merging adapter...", flush=True)
m=PeftModel.from_pretrained(m, ADAPTER)
m=m.merge_and_unload()
print("saving merged model ->", OUT, flush=True)
m.save_pretrained(OUT, safe_serialization=True)
AutoProcessor.from_pretrained(BASE).save_pretrained(OUT)
print("DONE merge in %.0fs" % (time.time()-t0), flush=True)
