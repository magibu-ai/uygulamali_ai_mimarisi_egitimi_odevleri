"""
Giresun kültürü veri seti üzerinde byte-level BPE tokenizer eğitir.

Neden byte-level BPE:
- Qwen ailesinin de kullandığı yaklaşım (byte-level BPE / BBPE).
- Baytlar üzerinde çalıştığı için Türkçe karakterlerde (ç, ğ, ı, ö, ş, ü)
  "bilinmeyen token" (UNK) sorunu oluşmaz; her metin temsil edilebilir.

Süreç:
1. Veri seti yüklenir (HF Hub'dan ya da yerel parquet'ten).
2. messages alanındaki tüm user + assistant metinleri bir corpus'a toplanır.
3. Byte-level BPE tokenizer eğitilir.
4. transformers PreTrainedTokenizerFast ile sarılır (chat template dahil).
5. Diske kaydedilir ve isteğe bağlı olarak HF Hub'a push edilir.

Kullanım:
    # HF'deki veri setinden eğit
    uv run python train_tokenizer.py --dataset KULLANICI/giresun_kultur

    # yerel parquet'ten eğit
    uv run python train_tokenizer.py --local data/turkish.parquet data/english.parquet

    # eğitip Hub'a push et
    uv run python train_tokenizer.py --dataset KULLANICI/giresun_kultur \
        --push KULLANICI/giresun-bpe-tokenizer
"""

import argparse
import os

from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders, processors
from transformers import PreTrainedTokenizerFast


# Özel token'lar. Chat/sohbet formatı ve fine-tune uyumu için standart set.
SPECIAL_TOKENS = [
    "<|endoftext|>",   # pad / eos
    "<|im_start|>",    # sohbet rol başlangıcı (Qwen tarzı)
    "<|im_end|>",      # sohbet rol bitişi
    "<|unk|>",
]


def load_corpus_from_hub(repo_id: str) -> list[str]:
    from datasets import load_dataset
    ds = load_dataset(repo_id)
    texts = []
    for split in ds:
        for row in ds[split]:
            for msg in row["messages"]:
                c = msg.get("content")
                if c:
                    texts.append(c)
    return texts


def load_corpus_from_parquet(paths: list[str]) -> list[str]:
    import pyarrow.parquet as pq
    texts = []
    for path in paths:
        rows = pq.read_table(path).to_pylist()
        for row in rows:
            for msg in row["messages"]:
                c = msg.get("content")
                if c:
                    texts.append(c)
    return texts


def train_tokenizer(corpus: list[str], vocab_size: int) -> Tokenizer:
    # Byte-level BPE modeli
    tokenizer = Tokenizer(models.BPE(unk_token="<|unk|>"))

    # Byte-level pre-tokenizer: metni baytlara açar, boşlukları da kodlar.
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()
    tokenizer.post_processor = processors.ByteLevel(trim_offsets=False)

    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=SPECIAL_TOKENS,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),  # 256 bayt
        show_progress=True,
        min_frequency=2,
    )

    tokenizer.train_from_iterator(corpus, trainer=trainer)
    return tokenizer


def wrap_fast(tokenizer: Tokenizer) -> PreTrainedTokenizerFast:
    # Qwen tarzı basit bir chat template (fine-tune için kullanışlı).
    chat_template = (
        "{% for message in messages %}"
        "{{ '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n' }}"
        "{% endfor %}"
        "{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
    )
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer,
        unk_token="<|unk|>",
        pad_token="<|endoftext|>",
        eos_token="<|im_end|>",
        bos_token=None,
        additional_special_tokens=["<|im_start|>", "<|im_end|>"],
        chat_template=chat_template,
    )
    return fast


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dataset", help="HF Hub veri seti repo id")
    src.add_argument("--local", nargs="+", help="Yerel parquet dosya yolları")
    ap.add_argument("--vocab-size", type=int, default=8000,
                    help="Hedef sözlük boyutu (varsayılan 8000)")
    ap.add_argument("--out", default="giresun-tokenizer",
                    help="Kayıt dizini")
    ap.add_argument("--push", metavar="REPO_ID",
                    help="HF Hub tokenizer repo id; verilirse push edilir")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()

    if args.dataset:
        corpus = load_corpus_from_hub(args.dataset)
    else:
        corpus = load_corpus_from_parquet(args.local)

    print(f"Corpus: {len(corpus)} metin parçası")
    total_chars = sum(len(t) for t in corpus)
    print(f"Toplam karakter: {total_chars}")

    tok = train_tokenizer(corpus, args.vocab_size)
    print(f"Eğitim tamam. Sözlük boyutu: {tok.get_vocab_size()}")

    fast = wrap_fast(tok)
    os.makedirs(args.out, exist_ok=True)
    fast.save_pretrained(args.out)
    print(f"Tokenizer '{args.out}/' altına kaydedildi.")

    # Hızlı doğrulama
    sample = "Giresun Adası, Karadeniz'in tek adasıdır. Kemençe ve horon meşhurdur."
    enc = fast(sample)
    dec = fast.decode(enc["input_ids"])
    print("\n--- Test ---")
    print("Girdi :", sample)
    print("Token :", len(enc["input_ids"]), "adet")
    print("Çözüm :", dec)
    print("Roundtrip eşleşti:", dec.strip() == sample.strip())

    if args.push:
        fast.push_to_hub(args.push, private=args.private)
        print(f"\nHub'a push edildi: https://huggingface.co/{args.push}")


if __name__ == "__main__":
    main()
