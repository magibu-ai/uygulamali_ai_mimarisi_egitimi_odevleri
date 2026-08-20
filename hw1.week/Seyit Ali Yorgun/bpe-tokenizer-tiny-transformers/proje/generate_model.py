"""Eğitilmiş herhangi bir modelden mineral/taş adı üret.

Kullanım:  python generate_model.py <model_key> [adet] [sıcaklık]
  örn:     python generate_model.py gemma4 20 0.8
  model_key: qwen3 | qwen3_5 | gemma4 | deepseek3

Karakter token'larıyla eğitilmiş modeli kullanır (bkz. train_model.py).
Checkpoint proje/checkpoints/<key>.pt; karakter sözlüğü eğitim verisinden kurulur.
"""

import os
import sys
import torch

REPO = os.path.join(os.path.dirname(__file__), "..", "single_letter_transformers")
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "mineraller.txt")
MODELS = {
    "qwen3":     ("qwen3",     "TinyQwen"),
    "qwen3_5":   ("qwen3_5",   "TinyQwen35"),
    "gemma4":    ("gemma4",    "TinyGemma"),
    "deepseek3": ("deepseek3", "TinyDeepSeek"),
}


def main():
    key = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    temperature = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8

    subdir, class_name = MODELS[key]
    sys.path.insert(0, os.path.abspath(os.path.join(REPO, subdir)))
    import model as model_mod
    from tokenizer import CharTokenizer
    ModelClass = getattr(model_mod, class_name)

    ckpt = torch.load(os.path.join(os.path.dirname(__file__), "checkpoints", f"{key}.pt"),
                      map_location="cpu", weights_only=False)
    tokenizer = CharTokenizer.from_file(DATA_FILE)
    model = ModelClass(ckpt["cfg"])
    model.load_state_dict(ckpt["model"])
    model.eval()

    start = torch.full((n, 1), tokenizer.newline_id, dtype=torch.long)
    with torch.no_grad():
        out = model.generate(start, max_new_tokens=ckpt["cfg"].max_seq_len,
                             temperature=temperature, top_k=None, eos_id=tokenizer.eos_id)
    for row in out.tolist():
        name = tokenizer.decode(row[1:]).split("\n")[0]
        if name:
            print(name)


if __name__ == "__main__":
    main()
