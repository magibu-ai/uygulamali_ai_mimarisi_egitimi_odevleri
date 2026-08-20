"""Phase 5: combine persona + tool data, split, push to HF as ..._finetune_v2.

messages/tools stored as JSON strings (robust vs Arrow's struggle with the
optional reasoning/tool_calls fields). Loader in Phase 6 json.loads them.
"""
import json, random
from datasets import Dataset, DatasetDict
random.seed(123)

def load(p): return [json.loads(l) for l in open(p, encoding="utf-8")]
persona = load("data/v2/persona_split.jsonl")
tools = load("data/v2/tools.jsonl")

def norm(r):
    return {"messages": json.dumps(r["messages"], ensure_ascii=False),
            "tools": json.dumps(r.get("tools"), ensure_ascii=False) if r.get("tools") else "",
            "enable_thinking": bool(r["enable_thinking"]),
            "source": r["source"]}

rows = [norm(r) for r in persona] + [norm(r) for r in tools]
random.shuffle(rows)

# small stratified validation split (monitor overfit)
val = [r for r in rows if r["source"] == "tool"][:15] + [r for r in rows if r["source"] == "persona"][:25]
val_ids = set(id(r) for r in val)
train = [r for r in rows if id(r) not in val_ids]

dd = DatasetDict({"train": Dataset.from_list(train), "validation": Dataset.from_list(val)})
print(dd)
# local backup
with open("data/v2/combined_train.jsonl", "w", encoding="utf-8") as f:
    for r in train: f.write(json.dumps(r, ensure_ascii=False) + "\n")

REPO = "gorkemergune/ayarlicazhocam_finetune_v2"
dd.push_to_hub(REPO, private=False)
print("pushed ->", REPO)
print(f"train={len(train)} val={len(val)} | persona={len(persona)} tools={len(tools)}")
