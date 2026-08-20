"""Phase 2: fetch v1 dataset, convert to Gemma-4-ready message schema.

Key correctness fix vs v1: Gemma 4's chat template reads the `reasoning` field,
NOT `thinking` (it silently drops `thinking`). So we rename thinking->reasoning.
Also dedupe and drop low-quality rows. Output: data/v2/base_clean.jsonl
(thinking kept on all rows here; Phase 3 decides the keep-ratio).
"""
import json, os, re, hashlib
from datasets import load_dataset

OUT_DIR = os.path.join("data", "v2")
os.makedirs(OUT_DIR, exist_ok=True)

ds = load_dataset("gorkemergune/ayarlicazhocam_finetune", split="train")
print("loaded", len(ds), "conversations")

def clean_msg(m):
    out = {"role": "user" if m["role"] == "user" else "assistant",
           "content": (m.get("content") or "").strip()}
    # v1 stored reasoning under 'thinking'; Gemma 4 wants 'reasoning'
    th = m.get("thinking")
    if th and out["role"] == "assistant":
        out["reasoning"] = th.strip()
    if m.get("tool_calls"):
        out["tool_calls"] = m["tool_calls"]
    return out

seen, rows, dropped = set(), [], {"dup": 0, "empty": 0, "bad_struct": 0}
for conv in ds:
    msgs = conv["messages"]
    if not msgs or len(msgs) < 2:
        dropped["bad_struct"] += 1; continue
    cm = [clean_msg(m) for m in msgs]
    # quality: assistant answers must be non-empty and not echo the user
    if any(m["role"] == "assistant" and len(m["content"]) < 2 for m in cm):
        dropped["empty"] += 1; continue
    key = hashlib.md5(json.dumps([(m["role"], m["content"]) for m in cm],
                                 ensure_ascii=False).encode()).hexdigest()
    if key in seen:
        dropped["dup"] += 1; continue
    seen.add(key)
    rows.append({"messages": cm})

path = os.path.join(OUT_DIR, "base_clean.jsonl")
with open(path, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

n_reason = sum(1 for r in rows for m in r["messages"] if m.get("reasoning"))
print(f"kept {len(rows)} | dropped {dropped}")
print(f"assistant msgs with reasoning: {n_reason}")
print("wrote", path)
