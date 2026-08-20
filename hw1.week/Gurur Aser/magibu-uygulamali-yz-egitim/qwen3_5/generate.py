import os
import sys
import torch

# Add parent directory to system path to import BPETokenizer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model import TinyQwen35
from train_tokenizer import BPETokenizer

CHECKPOINT = os.path.join(os.path.dirname(__file__), "tiny_qwen35.pt")
TOKENIZER_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "bpe_tokenizer.json"))


def load():
    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    tokenizer = BPETokenizer(TOKENIZER_FILE)
    model = TinyQwen35(ckpt["cfg"])
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, tokenizer


@torch.no_grad()
def generate_names(model, tokenizer, n, temperature, top_k=None):
    start = torch.full((n, 1), tokenizer.bos_token_id, dtype=torch.long)
    out = model.generate(start, max_new_tokens=model.cfg.max_seq_len,
                         temperature=temperature, top_k=top_k, eos_id=tokenizer.eos_token_id)
    names = [tokenizer.decode(row[1:]) for row in out.tolist()]
    return [n for n in names if n]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    temperature = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    model, tokenizer = load()
    for name in generate_names(model, tokenizer, n, temperature):
        print(name)


if __name__ == "__main__":
    main()
