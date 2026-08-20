"""Generate Turkish names from a trained checkpoint.

Run:  python generate.py            # 20 names, default settings
      python generate.py 50         # 50 names
      python generate.py 50 0.8     # 50 names, temperature 0.8

Lower temperature -> safer, more common names. Higher -> more varied/creative.
"""
import os
import sys
import torch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model"))

from model import TinyQwen
from transformers import AutoTokenizer

CHECKPOINT = "tiny_biyoloji.pt"


def load():
    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    tokenizer = AutoTokenizer.from_pretrained("biyoloji_tokenizer")
    model = TinyQwen(ckpt["cfg"])
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, tokenizer


@torch.no_grad()
def generate_names(model, tokenizer, n: int, temperature: float, top_k=None):
    # Every name starts from the newline (start-of-name) token.
    newline_id = tokenizer.encode("\n")[0]
    start = torch.full((n, 1), newline_id, dtype=torch.long)
    out = model.generate(start, max_new_tokens=model.cfg.max_seq_len,
                         temperature=temperature, top_k=top_k, eos_id=newline_id)
    names = []
    for row in out.tolist():
        # Drop the leading newline, then keep everything up to the next newline.
        name = tokenizer.decode(row[1:]).split("\n")[0]
        if name:
            names.append(name)
    return names


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    temperature = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    model, tokenizer = load()
    for name in generate_names(model, tokenizer, n, temperature):
        print(name)


if __name__ == "__main__":
    main()
