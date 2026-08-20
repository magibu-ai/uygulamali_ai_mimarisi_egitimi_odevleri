# -*- coding: utf-8 -*-
# Konum: C:\Magibu\URET.py
import os, sys, importlib
import torch

BURASI = os.path.dirname(os.path.abspath(__file__))
REPO   = os.path.join(BURASI, "single_letter_transformers")
os.chdir(REPO)
DEVICE = "cpu"

# --- SADECE bu üç satırı değiştir ---
FOLDER = "qwen3"
CLS    = "TinyQwen"
CKPT   = "qwen3/tiny_qwen.pt"
# qwen3     -> TinyQwen     -> qwen3/tiny_qwen.pt
# qwen3_5   -> TinyQwen35   -> qwen3_5/tiny_qwen35.pt
# gemma4    -> TinyGemma    -> gemma4/tiny_gemma.pt
# deepseek3 -> TinyDeepSeek -> deepseek3/tiny_deepseek.pt

ADET     = 20
SICAKLIK = 0.8

sys.path.insert(0, os.path.join(REPO, FOLDER))
model_mod = importlib.import_module("model")
tok_mod   = importlib.import_module("tokenizer")
ModelClass    = getattr(model_mod, CLS)
CharTokenizer = tok_mod.CharTokenizer

ckpt = torch.load(CKPT, map_location=DEVICE, weights_only=False)
tok = CharTokenizer(ckpt["chars"])
model = ModelClass(ckpt["cfg"]).to(DEVICE)
model.load_state_dict(ckpt["model"]); model.eval()

start = torch.full((ADET, 1), tok.eos_id, dtype=torch.long, device=DEVICE)
with torch.no_grad():
    out = model.generate(start, max_new_tokens=ckpt["cfg"].max_seq_len,
                         temperature=SICAKLIK, eos_id=tok.eos_id)

print(f"--- {CLS} üretimi ---")
for row in out.tolist():
    print(tok.decode(row[1:]).split("\n")[0])