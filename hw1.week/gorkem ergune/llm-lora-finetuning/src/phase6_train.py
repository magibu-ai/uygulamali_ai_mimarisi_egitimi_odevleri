"""Phase 6: QLoRA SFT of Gemma 4 E4B (text-only) for ayarlicazhocam v2.

- Verified 12GB config: 4-bit LM on GPU, towers + elastic PLE on CPU, embeds bf16.
- Completion-only masking via INCREMENTAL prefixes (no fragile string markers -
  the v1 failure mode). Each assistant span is unmasked only after asserting the
  prefix is a true token-prefix of the full sequence.
- Per-row enable_thinking / tools / preserve_thinking honored at tokenize time.

Run smoke:  python src/phase6_train.py --smoke
Run full:   python src/phase6_train.py
"""
import os, sys, json, math, random, time
import torch
from torch.utils.data import DataLoader
from transformers import Gemma4ForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset
import bitsandbytes as bnb
sys.path.insert(0, os.path.dirname(__file__))
from mask_utils import build_labels

SMOKE = "--smoke" in sys.argv
MODEL = "google/gemma-4-E4B-it"
MAX_LEN = 1024
OUT_DIR = "outputs/gemma4-e4b-ayarlicazhocam-v2"
EPOCHS = 2
LR = 2e-4
GRAD_ACCUM = 16
random.seed(0); torch.manual_seed(0)

# ------------------------------- model --------------------------------------
def load_model():
    SKIP = ["vision_tower", "audio_tower", "embed_vision", "embed_audio", "lm_head"]
    bnbc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        llm_int8_skip_modules=SKIP, llm_int8_enable_fp32_cpu_offload=True)
    dm = {"model.language_model": 0, "lm_head": 0, "model.vision_tower": "cpu",
          "model.audio_tower": "cpu", "model.embed_vision": "cpu", "model.embed_audio": "cpu",
          "model.language_model.embed_tokens_per_layer": "cpu"}
    m = Gemma4ForConditionalGeneration.from_pretrained(MODEL, quantization_config=bnbc,
        device_map=dm, torch_dtype=torch.bfloat16)
    m = prepare_model_for_kbit_training(m, use_gradient_checkpointing=True)
    for n, mod in m.named_modules():
        if n.endswith(("embed_tokens", "embed_tokens_per_layer")) and hasattr(mod, "weight"):
            mod.to(torch.bfloat16)
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$")
    m = get_peft_model(m, lora)
    m.gradient_checkpointing_enable(); m.enable_input_require_grads()
    m.config.use_cache = False
    m.print_trainable_parameters()
    return m

tok = AutoProcessor.from_pretrained(MODEL)
tok = tok.tokenizer if hasattr(tok, "tokenizer") else tok

# --------------------------- tokenize + mask --------------------------------
def build_example(row):
    msgs = json.loads(row["messages"])
    tools = json.loads(row["tools"]) if row["tools"] else None
    et = row["enable_thinking"]
    ids = tok.apply_chat_template(msgs, tools=tools, enable_thinking=et,
        preserve_thinking=True, tokenize=True, return_dict=True)["input_ids"]
    if len(ids) > MAX_LEN:
        return None  # drop over-long rather than truncate mid-response
    labels = build_labels(ids)   # token-level state machine (see mask_utils)
    if all(l == -100 for l in labels):
        return None
    return {"input_ids": ids, "labels": labels, "source": row["source"]}

def prepare(split):
    ds = load_dataset("gorkemergune/ayarlicazhocam_finetune_v2", split=split)
    out, dropped = [], 0
    for row in ds:
        e = build_example(row)
        if e is None: dropped += 1
        else: out.append(e)
    print(f"[{split}] kept {len(out)} dropped {dropped}")
    return out

def collate(batch):
    maxlen = max(len(b["input_ids"]) for b in batch)
    pad = tok.pad_token_id or 0
    ids, lbl, att = [], [], []
    for b in batch:
        n = maxlen - len(b["input_ids"])
        ids.append(b["input_ids"] + [pad] * n)
        lbl.append(b["labels"] + [-100] * n)
        att.append([1] * len(b["input_ids"]) + [0] * n)
    return (torch.tensor(ids), torch.tensor(lbl), torch.tensor(att))

# -------------------------------- train -------------------------------------
def main():
    train = prepare("train"); val = prepare("validation")
    # oversample the scarce tool examples (~7% -> ~18%) so tool-calling is learned well
    OVERSAMPLE_TOOLS = 3
    tools_rows = [e for e in train if e["source"] == "tool"]
    train = train + tools_rows * (OVERSAMPLE_TOOLS - 1)
    random.shuffle(train)
    print(f"after tool oversample x{OVERSAMPLE_TOOLS}: train={len(train)} (tools now {sum(1 for e in train if e['source']=='tool')})")
    if SMOKE:
        train = train[:24]
    # masking coverage sanity: avg % of tokens that are supervised
    cov = sum(sum(1 for x in e["labels"] if x != -100) / len(e["labels"]) for e in train) / len(train)
    print(f"avg supervised-token fraction: {cov:.1%}  (v1 bug would show ~0%)")

    model = load_model()
    dl = DataLoader(train, batch_size=1, shuffle=True, collate_fn=collate)
    steps_per_epoch = math.ceil(len(dl) / GRAD_ACCUM)
    total_steps = steps_per_epoch * (1 if SMOKE else EPOCHS)
    opt = bnb.optim.AdamW8bit([p for p in model.parameters() if p.requires_grad], lr=LR)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=LR, total_steps=total_steps,
        pct_start=0.03, anneal_strategy="cos", div_factor=10, final_div_factor=10)

    model.train(); t0 = time.time(); step = 0; micro = 0; running = 0.0
    torch.cuda.reset_peak_memory_stats()
    for epoch in range(1 if SMOKE else EPOCHS):
        for ids, lbl, att in dl:
            ids, lbl, att = ids.to(0), lbl.to(0), att.to(0)
            out = model(input_ids=ids, attention_mask=att, labels=lbl)
            (out.loss / GRAD_ACCUM).backward()
            running += out.loss.item(); micro += 1
            if micro % GRAD_ACCUM == 0:
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step(); sched.step(); opt.zero_grad(); step += 1
                if step % 5 == 0 or SMOKE:
                    print(f"epoch {epoch} step {step}/{total_steps} loss {running/GRAD_ACCUM/ (5 if step%5==0 and not SMOKE else 1):.4f} "
                          f"lr {sched.get_last_lr()[0]:.2e} peak {torch.cuda.max_memory_allocated()/1e9:.1f}GB "
                          f"{(time.time()-t0)/60:.1f}min", flush=True)
                    running = 0.0
            if SMOKE and step >= 3:
                break
        if SMOKE:
            break
    # quick val loss
    model.eval(); vloss = 0.0; n = 0
    with torch.no_grad():
        for ids, lbl, att in DataLoader(val, batch_size=1, collate_fn=collate):
            o = model(input_ids=ids.to(0), attention_mask=att.to(0), labels=lbl.to(0))
            vloss += o.loss.item(); n += 1
    print(f"val loss: {vloss/max(n,1):.4f}")

    if not SMOKE:
        os.makedirs(OUT_DIR, exist_ok=True)
        model.save_pretrained(OUT_DIR); tok.save_pretrained(OUT_DIR)
        print("saved adapter ->", OUT_DIR)
    print(f"DONE in {(time.time()-t0)/60:.1f}min | peak {torch.cuda.max_memory_allocated()/1e9:.1f}GB")

if __name__ == "__main__":
    main()
