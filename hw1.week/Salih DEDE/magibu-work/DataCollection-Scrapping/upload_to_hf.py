import json
import os
import sys

from huggingface_hub import HfApi, create_repo

from fill_thinking import load_env_file

MERGED_INPUT_FILE = "trendyolProductAsistantQA.json"
DATASET_DIR = "hf_dataset"
DATA_FILE = os.path.join(DATASET_DIR, "data", "train.jsonl")
README_FILE = os.path.join(DATASET_DIR, "README.md")
ENV_FILE = ".env"

README_TEMPLATE = """---
language:
- tr
license: other
task_categories:
- text-generation
tags:
- e-ticaret
- musteri-hizmetleri
- turkce
- trendyol
- chain-of-thought
pretty_name: Trendyol Marangoz Ürünleri Soru-Cevap Asistanı
size_categories:
- 1K<n<10K
---

# Trendyol Marangoz Ürünleri Soru-Cevap Asistanı

Bu veri kümesi, Trendyol'daki marangozluk/ahşap ürün kategorisindeki
"Satıcıya Sor" bölümünden toplanan gerçek müşteri sorusu ve satıcı cevabı
çiftlerinden oluşur. Her örneğe, satıcının cevaba nasıl vardığını gösteren,
`{model}` modeli ile (OpenRouter üzerinden) üretilmiş sentetik bir
`thinking` (iç muhakeme) alanı eklenmiştir.

## İçerik

- **Toplam örnek sayısı:** {n}
- **Sütun:** `conversations` — `[user_mesajı, assistant_mesajı]` şeklinde
  iki mesajlık bir liste. Her mesaj `content`, `images`, `role`,
  `thinking`, `tool_calls` alanlarını içerir.
- `user` mesajının `thinking` alanı her zaman `null`'dır.
- `assistant` mesajının `content` alanı **gerçek** satıcı cevabıdır;
  `thinking` alanı ise LLM tarafından üretilmiş **sentetik** bir
  muhakeme zinciridir (satıcının gerçek iç sesi değildir).

## Üretim süreci

1. Ürün sayfaları ve "Satıcıya Sor" soru-cevapları Selenium ile scrape
   edildi (`TrendyolScrapper.py`).
2. Her soru-cevap için, ürün özellikleri bağlam olarak verilerek
   OpenRouter API'si üzerinden bir LLM'e "bu cevaba varmadan önceki iç
   muhakemeyi yaz" görevi verildi (`fill_thinking.py`).
3. Sonuçlar `conversations` sütunu altında JSONL formatında birleştirildi.

## Kullanım alanı ve sınırlamalar

- Bu veri kümesi eğitim/araştırma ve portföy amaçlıdır.
- `thinking` alanları sentetik olup gerçek satıcı düşüncesini yansıtmaz;
  model çıktısı olarak değerlendirilmelidir.
- Veriler halka açık bir e-ticaret platformundan toplanmıştır; ticari
  kullanım öncesi ilgili platformun kullanım şartlarını gözden
  geçirmeniz önerilir.
"""


def convert_to_jsonl():
    with open(MERGED_INPUT_FILE, "r", encoding="utf-8") as f:
        diyaloglar = json.load(f)

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        for diyalog in diyaloglar:
            f.write(json.dumps({"conversations": diyalog}, ensure_ascii=False) + "\n")

    return len(diyaloglar)


def write_readme(n, model):
    os.makedirs(DATASET_DIR, exist_ok=True)
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(README_TEMPLATE.format(n=n, model=model))


def main():
    load_env_file(ENV_FILE)

    token = os.environ.get("HF_TOKEN")
    repo_id = os.environ.get("HF_REPO_ID")
    private = os.environ.get("HF_PRIVATE", "false").strip().lower() == "true"
    model = os.environ.get("OPENROUTER_MODEL", "bir LLM")

    if not token or not repo_id:
        print("HF_TOKEN ve HF_REPO_ID ortam değişkenleri gerekli (.env dosyasına ekle).")
        sys.exit(1)

    if not os.path.exists(MERGED_INPUT_FILE):
        print(f"{MERGED_INPUT_FILE} bulunamadı. Önce fill_thinking.py çalıştırılmalı.")
        sys.exit(1)

    n = convert_to_jsonl()
    write_readme(n, model)

    create_repo(repo_id, repo_type="dataset", private=private, token=token, exist_ok=True)

    api = HfApi(token=token)
    api.upload_folder(
        repo_id=repo_id,
        folder_path=DATASET_DIR,
        repo_type="dataset",
        commit_message=f"{n} örnek ile veri kümesi güncellendi",
    )

    visibility = "private" if private else "public"
    print(f"Yüklendi: https://huggingface.co/datasets/{repo_id} ({visibility}, {n} örnek)")


if __name__ == "__main__":
    main()
