"""Repodaki BÜTÜN dil modellerini KARAKTER token'larıyla sırayla eğit.

Kullanım:  python train_all.py

Her modeli ayrı bir subprocess'te çalıştırır (train_model.py). Böylece her modelin
aynı adlı dosyaları — config.py, model.py, tokenizer.py ... — birbirine karışmadan
kendi klasöründen import edilir.

Eğitilenler: qwen3, qwen3_5, gemma4, deepseek3 (hepsi dil modeli).
Eğitilmeyenler: acestep (ses/müzik üretimi — metin göreviyle alakasız),
lora (bağımsız model değil, fine-tune eklentisi).

Ön koşul yok: karakter sözlüğü doğrudan data/mineraller.txt'ten kurulur.
BPE (hf_bpe.py) ayrı bir ödevdir ve buraya girmez.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ["qwen3", "qwen3_5", "gemma4", "deepseek3"]


def main():
    for key in KEYS:
        print(f"\n{'='*60}\n### {key} eğitiliyor\n{'='*60}")
        subprocess.run([sys.executable, os.path.join(HERE, "train_model.py"), key], check=True)


if __name__ == "__main__":
    main()
