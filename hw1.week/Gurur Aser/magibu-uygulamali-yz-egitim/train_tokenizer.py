"""İthaki Bilimkurgu Klasikleri veri setinden Byte-Level BPE tokenizer eğitir ve Hugging Face'e yükler."""
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.trainers import BpeTrainer
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.decoders import ByteLevel as ByteLevelDecoder
from huggingface_hub import HfApi
import pandas as pd

DATASET_ID = "gururaser/ithaki-bilimkurgu-klasikleri"
CSV_PATH = f"hf://datasets/{DATASET_ID}/ithaki_bilimkurgu_klasikleri_ozetli.csv"
TOKENIZER_REPO_ID = "gururaser/ithaki-bpe-tokenizer"
OUTPUT_PATH = "ithaki_bpe_tokenizer.json"
VOCAB_SIZE = 1000


def corpus_olustur() -> list[str]:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    metinler = df["kitap_adi"].astype(str) + ". " + df["yazar"].astype(str) + ". " + df["ozet"].astype(str)
    return metinler.tolist()


def bpe_tokenizer_egit(corpus: list[str], vocab_size: int = VOCAB_SIZE) -> Tokenizer:
    # ByteLevel pre-tokenizer herhangi bir karakteri (Türkçe dahil) sorunsuz işler
    # ve modern LLM tokenizer'larıyla (GPT, Llama, Qwen vb.) aynı yaklaşımı kullanır.
    tokenizer = Tokenizer(BPE(unk_token="<unk>"))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False)
    tokenizer.decoder = ByteLevelDecoder()

    trainer = BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=["<unk>", "<pad>", "<bos>", "<eos>"],
    )
    tokenizer.train_from_iterator(corpus, trainer, length=len(corpus))
    return tokenizer


def model_karti(vocab_size: int) -> str:
    return f"""---
license: cc-by-nc-4.0
language:
- tr
datasets:
- {DATASET_ID}
tags:
- tokenizers
- bpe
---

# İthaki Bilimkurgu Klasikleri BPE Tokenizer

[`{DATASET_ID}`](https://huggingface.co/datasets/{DATASET_ID}) veri setindeki
kitap adı, yazar ve özet metinlerinden eğitilmiş byte-level BPE tokenizer.
Vocab boyutu: {vocab_size}.

**Eğitim amaçlı oluşturulmuştur.**

## Kullanım

```python
from tokenizers import Tokenizer
tokenizer = Tokenizer.from_file("tokenizer.json")
tokenizer.encode("Isaac Asimov").tokens
```
"""


def main():
    print(f"'{DATASET_ID}' veri seti Hugging Face'ten okunuyor...")
    corpus = corpus_olustur()
    print(f"{len(corpus)} satırlık corpus hazır.")

    tokenizer = bpe_tokenizer_egit(corpus)
    tokenizer.save(OUTPUT_PATH)
    vocab_size = tokenizer.get_vocab_size()
    print(f"Tokenizer kaydedildi -> {OUTPUT_PATH} (vocab_size={vocab_size})")

    print("\n--- Örnek tokenizasyon ---")
    for ornek in ["Nemesis kitabının yazarı kimdir?", "Bilimkurgu Klasikleri", "Isaac Asimov"]:
        print(f"'{ornek}' -> {tokenizer.encode(ornek).tokens}")

    api = HfApi()
    api.create_repo(repo_id=TOKENIZER_REPO_ID, repo_type="model", exist_ok=True)
    api.upload_file(
        path_or_fileobj=OUTPUT_PATH,
        path_in_repo="tokenizer.json",
        repo_id=TOKENIZER_REPO_ID,
        repo_type="model",
    )
    api.upload_file(
        path_or_fileobj=model_karti(vocab_size).encode("utf-8"),
        path_in_repo="README.md",
        repo_id=TOKENIZER_REPO_ID,
        repo_type="model",
    )

    print(f"\nYüklendi: https://huggingface.co/{TOKENIZER_REPO_ID}")


if __name__ == "__main__":
    main()
