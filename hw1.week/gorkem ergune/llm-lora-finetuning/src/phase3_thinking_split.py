"""Phase 3: down-sample thinking to ~20% (user decision).

v1 data has reasoning on 100% of examples. Keep reasoning on ~20% (rendered
think-on with <|think|>), strip it from ~80% (plain, think-off). Each row gets
an `enable_thinking` flag consumed at tokenization time so the model learns BOTH
modes and Gemma 4's native think on/off control is preserved.
"""
import json, os, random
random.seed(42)

SRC = "data/v2/base_clean.jsonl"
OUT = "data/v2/persona_split.jsonl"
THINK_RATIO = 0.20

rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
random.shuffle(rows)
n_think = round(len(rows) * THINK_RATIO)

out = []
for i, r in enumerate(rows):
    think_on = i < n_think
    msgs = []
    for m in r["messages"]:
        m = dict(m)
        if not think_on:
            m.pop("reasoning", None)          # strip thinking -> plain answer
        msgs.append(m)
    out.append({"messages": msgs, "enable_thinking": think_on, "source": "persona"})

random.shuffle(out)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

kept = sum(1 for r in out if r["enable_thinking"])
print(f"total {len(out)} | think-on {kept} ({kept/len(out):.0%}) | think-off {len(out)-kept}")
print("wrote", OUT)
