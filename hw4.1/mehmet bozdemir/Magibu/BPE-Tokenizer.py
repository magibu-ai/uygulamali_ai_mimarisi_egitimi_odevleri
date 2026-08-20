# -*- coding: utf-8 -*-
# Konum: C:\Magibu\ODEV-2.py
# Calistir: python ODEV-2.py
#           python ODEV-2.py "Kendi cumleniz."
#
# Byte_Pair_Encoding_tokenization.ipynb icindeki BPE kodu,
# Turkce bir korpus uzerinde egitilir. gpt2 tokenizer KULLANILMAZ.

import os, sys, json, re, urllib.request
from collections import defaultdict

BURASI     = os.path.dirname(os.path.abspath(__file__))
CORPUS_TXT = os.path.join(BURASI, "data_bpe", "turkce_corpus.txt")
TOKENIZER  = os.path.join(BURASI, "bpe_tokenizer.json")
VOCAB_SIZE = 1000

TQUAD   = "https://raw.githubusercontent.com/TQuad/turkish-nlp-qa-dataset/master/"
WIKINER = ("https://raw.githubusercontent.com/turkish-nlp-suite/"
           "Turkish-Wiki-NER-Dataset/main/Turkish-Wiki-NER-Dataset/")


# ======================= 1. VERI SETI =======================
def corpus_indir():
    """TQuAD (bilim tarihi) + WikiNER (Wikipedia) -> tek txt."""
    metinler = []

    for dosya in ["train-v0.1.json", "dev-v0.1.json"]:
        with urllib.request.urlopen(TQUAD + dosya, timeout=60) as r:
            veri = json.loads(r.read().decode("utf-8"))
        for konu in veri["data"]:
            for p in konu["paragraphs"]:
                metinler.append(p["context"])
    print(f"  TQuAD   : {len(metinler):>6} paragraf")

    n = len(metinler)
    for dosya in ["train.conll", "dev.conll", "test.conll"]:
        with urllib.request.urlopen(WIKINER + dosya, timeout=60) as r:
            icerik = r.read().decode("utf-8")
        tokenler = []
        for satir in icerik.split("\n"):
            if not satir.strip():
                if tokenler:
                    metinler.append(re.sub(r"\s+([,.!?;:'])", r"\1", " ".join(tokenler)))
                    tokenler = []
            else:
                tokenler.append(satir.split("\t")[0])
    print(f"  WikiNER : {len(metinler)-n:>6} cumle")
    return metinler


def corpus_hazirla():
    os.makedirs(os.path.dirname(CORPUS_TXT), exist_ok=True)
    if os.path.exists(CORPUS_TXT):
        metin = open(CORPUS_TXT, encoding="utf-8").read()
        print(f"[veri] {CORPUS_TXT} ({len(metin):,} karakter)")
        return metin.split("\n")

    print("[veri] Turkce korpus indiriliyor...")
    metinler = corpus_indir()
    with open(CORPUS_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(metinler))
    print(f"[veri] {sum(len(m) for m in metinler):,} karakter -> {CORPUS_TXT}")
    return metinler


# ============ 2. NORMALIZASYON (course 6/4) ============
# gpt2'nin pre_tokenizer'i yok, o yuzden metni kendimiz sadelestiriyoruz:
# kucuk harf + Turkce alfabe disi karakterleri at. Bu olmazsa alfabe 287
# karaktere cikiyor (Arapca ceviriyazi, semboller) ve vocab'in ucte biri cope gidiyor.
IZINLI = set("abcçdefgğhıijklmnoöprsştuüvyzqwx") | set("0123456789") | set(" .,;:!?'-")

def temizle(metin):
    metin = (metin.replace("I", "ı").replace("İ", "i").replace("Ç", "ç")
                  .replace("Ş", "ş").replace("Ğ", "ğ").replace("Ü", "ü")
                  .replace("Ö", "ö").lower())
    for a, b in [("’", "'"), ("‘", "'"), ("“", " "), ("”", " "), ("–", "-"), ("—", "-")]:
        metin = metin.replace(a, b)
    return "".join(c if c in IZINLI else " " for c in metin)


# ======================= 3. ipynb KODU =======================
def egit(corpus):
    # --- word_freqs ---  (gpt2 pre_tokenize_str yerine .split())
    word_freqs = defaultdict(int)
    for text in corpus:
        for word in temizle(text).split():
            word_freqs[word] += 1
    print(f"[bpe] benzersiz kelime: {len(word_freqs):,}")

    # --- alphabet ---
    alphabet = []
    for word in word_freqs.keys():
        for letter in word:
            if letter not in alphabet:
                alphabet.append(letter)
    alphabet.sort()
    print(f"[bpe] alfabe ({len(alphabet)}): {''.join(alphabet)}")

    vocab = ["<|endoftext|>"] + alphabet.copy()
    splits = {word: [c for c in word] for word in word_freqs.keys()}

    def compute_pair_freqs(splits):
        pair_freqs = defaultdict(int)
        for word, freq in word_freqs.items():
            split = splits[word]
            if len(split) == 1:
                continue
            for i in range(len(split) - 1):
                pair = (split[i], split[i + 1])
                pair_freqs[pair] += freq
        return pair_freqs

    def merge_pair(a, b, splits):
        for word in word_freqs:
            split = splits[word]
            if len(split) == 1:
                continue
            i = 0
            while i < len(split) - 1:
                if split[i] == a and split[i + 1] == b:
                    split = split[:i] + [a + b] + split[i + 2:]
                else:
                    i += 1
            splits[word] = split
        return splits

    # --- egitim dongusu ---
    merges = {}
    print(f"[bpe] egitim basliyor (vocab_size={VOCAB_SIZE}, ~5 dakika)...")
    while len(vocab) < VOCAB_SIZE:
        pair_freqs = compute_pair_freqs(splits)
        best_pair = ""
        max_freq = None
        for pair, freq in pair_freqs.items():
            if max_freq is None or max_freq < freq:
                best_pair = pair
                max_freq = freq
        splits = merge_pair(*best_pair, splits)
        merges[best_pair] = best_pair[0] + best_pair[1]
        vocab.append(best_pair[0] + best_pair[1])
        if len(merges) % 100 == 0:
            print(f"  merge {len(merges):>4}  vocab {len(vocab):>4}  son: {merges[best_pair]!r}")
    print(f"[bpe] bitti: {len(merges)} merge, vocab {len(vocab)}")
    return vocab, merges


def tokenize(text, merges):
    pre_tokenized_text = temizle(text).split()
    splits = [[l for l in word] for word in pre_tokenized_text]
    for pair, merge in merges.items():
        for idx, split in enumerate(splits):
            i = 0
            while i < len(split) - 1:
                if split[i] == pair[0] and split[i + 1] == pair[1]:
                    split = split[:i] + [merge] + split[i + 2:]
                else:
                    i += 1
            splits[idx] = split
    return sum(splits, [])


# ======================= 4. ANA =======================
def main():
    if os.path.exists(TOKENIZER):
        d = json.load(open(TOKENIZER, encoding="utf-8"))
        vocab  = list(d["vocab"].keys())
        merges = {tuple(k.split(" ")): v for k, v in d["merges"].items()}
        print(f"[tokenizer] {TOKENIZER} yuklendi (vocab={len(vocab)})")
    else:
        corpus = corpus_hazirla()
        vocab, merges = egit(corpus)
        # --- vocab -> ID (index = ID) ---
        with open(TOKENIZER, "w", encoding="utf-8") as f:
            json.dump({"vocab":  {t: i for i, t in enumerate(vocab)},
                       "merges": {f"{a} {b}": m for (a, b), m in merges.items()}},
                      f, ensure_ascii=False, indent=1)
        print(f"[kayit] {TOKENIZER}")
        print("\nILK 20 MERGE:", list(merges.values())[:20])

    stoi = {t: i for i, t in enumerate(vocab)}

    cumleler = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else [
        "İslam dünyasında bilim ve teknoloji gelişmiştir.",
        "Kitapları okuyabilirsiniz.",
        "Bursa Uludağ Üniversitesi bilgisayar mühendisliği",
    ]
    for c in cumleler:
        tok = tokenize(c, merges)
        print(f"\nMETIN : {c}")
        print(f"TOKEN : {tok}")
        print(f"ID    : {[stoi.get(t, 0) for t in tok]}")


if __name__ == "__main__":
    main()