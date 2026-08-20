"""
05_build_finetune_dataset.py

Seed QA verisini ("data/seed_qa_examples.json") veya QA_Data.json verisini
"messages" formatına getirip train.jsonl ve valid.jsonl dosyalarını oluşturur.
"""
import os
import json
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
SEED_PATH = os.path.join(ROOT, "data", "seed_qa_examples.json")
OUT_DIR = os.path.join(ROOT, "dataset")

SYSTEM_PROMPT = "Sen eczacılık ve ilaç bilgisi konusunda uzman, dikkatli ve doğru bilgi veren bir asistansın."

VALID_RATIO = 0.1
SEED = 42


def to_messages(system, user, assistant):
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def load_seed_examples():
    if not os.path.exists(SEED_PATH):
        print(f"UYARI: {SEED_PATH} bulunamadi, seed ornekler atlanacak.")
        return []
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [to_messages(ex.get("system", SYSTEM_PROMPT), ex["user"], ex["assistant"]) for ex in raw]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    random.seed(SEED)

    all_examples = load_seed_examples()
    print(f"Seed ornekler: {len(all_examples)}")

    if not all_examples:
        print("Hic ornek uretilemedi, cikiliyor.")
        return

    random.shuffle(all_examples)
    n_valid = max(1, int(len(all_examples) * VALID_RATIO))
    valid_examples = all_examples[:n_valid]
    train_examples = all_examples[n_valid:]

    train_path = os.path.join(OUT_DIR, "train.jsonl")
    valid_path = os.path.join(OUT_DIR, "valid.jsonl")

    with open(train_path, "w", encoding="utf-8") as f:
        for ex in train_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(valid_path, "w", encoding="utf-8") as f:
        for ex in valid_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"train: {len(train_examples)} ornek -> {train_path}")
    print(f"valid: {len(valid_examples)} ornek -> {valid_path}")


if __name__ == "__main__":
    main()
