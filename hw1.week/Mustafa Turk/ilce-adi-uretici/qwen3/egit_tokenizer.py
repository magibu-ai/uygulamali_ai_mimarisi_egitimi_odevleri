"""Train the BPE tokenizer and save it as a standalone artifact.

Run:  python egit_tokenizer.py           # vocab_size=300
      python egit_tokenizer.py 500       # vocab_size=500

Writes tokenizer.json (vocab + merge rules) and prints what BPE learned.
The model does not need this file -- train.py retrains the tokenizer from
the data -- but it is the deliverable for the tokenizer assignment, and it
lets you inspect the vocabulary without touching the model.
"""

import json
import os
import sys

from bpe_tokenizer import BPETokenizer

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "temiz_isimler.txt")
OUT_FILE = os.path.join(os.path.dirname(__file__), "tokenizer.json")


def main():
    vocab_size = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    print(f"Veri:  {DATA_FILE}")
    print(f"Hedef vocab_size: {vocab_size}")
    print("Eğitiliyor...\n")

    tok = BPETokenizer.from_file(DATA_FILE, vocab_size=vocab_size)

    # ---- kaydet -----------------------------------------------------------
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tok.chars, f, ensure_ascii=False, indent=1)
    print(f"-> {OUT_FILE} yazıldı")

    # ---- ne öğrendi? ------------------------------------------------------
    text = open(DATA_FILE, encoding="utf-8").read()
    names = [l for l in text.split("\n") if l]
    ids = tok.encode(text)

    print(f"\nvocab_size   : {tok.vocab_size}")
    print(f"merge kuralı : {len(tok.merges)}")
    print(f"eos_id       : {tok.eos_id}  ('\\n')")

    print("\nİlk 10 merge kuralı (= en sık geçen ikililer):")
    for i, (a, b) in enumerate(tok.merges[:10]):
        print(f"  {i + 1:2d}. {a!r} + {b!r} -> {a + b!r}")

    print("\nÖğrenilen en uzun 15 token:")
    uzun = sorted((t for t in tok.vocab if len(t) > 1), key=len, reverse=True)[:15]
    print("  " + ", ".join(uzun))

    print("\nSıkıştırma (tüm dosya, '\\n' ayırıcılar dahil):")
    print(f"  karakter : {len(text):7d}")
    print(f"  BPE token: {len(ids):7d}   ({len(text) / len(ids):.2f}x kısa)")

    # İsim başına: ayırıcı '\n' hariç, sadece ismin kendisi.
    bpe_isim = sum(len(tok._tokenize_word(n)) for n in names) / len(names)
    kar_isim = sum(len(n) for n in names) / len(names)
    print(f"\nİsim başına ('\\n' hariç):")
    print(f"  karakter : {kar_isim:.1f}")
    print(f"  BPE token: {bpe_isim:.1f}   ({kar_isim / bpe_isim:.2f}x kısa)")

    print("\nÖrnek bölümlemeler:")
    for w in ["yeşilköy", "kızılcahamam", "yukarıçayır", "zonguldak"]:
        print(f"  {w:15s} -> {'+'.join(tok._tokenize_word(w))}")


if __name__ == "__main__":
    main()
