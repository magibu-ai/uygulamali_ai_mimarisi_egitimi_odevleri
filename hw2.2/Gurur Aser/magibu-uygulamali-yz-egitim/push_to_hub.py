"""Hugging Face Hub Uploader for Synthetic E-Commerce NER Dataset.

Uploads the generated JSONL dataset and creates a detailed dataset card (README.md).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from huggingface_hub import HfApi, create_repo


def generate_dataset_card_readme(repo_id: str, sample_record: Dict[str, Any], total_records: int) -> str:
    """Generate markdown README.md for Hugging Face Dataset Card."""
    sample_json = json.dumps(sample_record, ensure_ascii=False, indent=2)

    readme_content = f"""---
license: mit
language:
- tr
tags:
- e-commerce
- ner
- named-entity-recognition
- synthetic
- nemo-data-designer
- deepseek
size_categories:
- 1K<n<10K
task_categories:
- token-classification
- text-classification
---

# 🛒 Natural Turkish E-Commerce NER Dataset ({total_records} Samples)

Bu veriseti, **NVIDIA NeMo Data Designer** ve **Hugging Face Inference Provider** (`deepseek-ai/DeepSeek-V4-Flash:fireworks-ai`) kullanılarak üretilmiş sentetik ve yüksek kaliteli doğal Türkçe e-ticaret ürün adları ile Named Entity Recognition (NER) etiketlerini içermektedir.

## 📊 Veriseti Özeti

- **Toplam Kayıt Sayısı**: {total_records} adet
- **Dil**: Türkçe (TR)
- **Kategoriler**: Ayakkabı, Çanta, Giyim, Aksesuar, Elektronik, Ev & Mutfak, Mobilya & Dekorasyon, Kozmetik, Kişisel Bakım, Spor & Outdoor
- **Format**: JSON Lines (`.jsonl`)

## 🏷️ NER Etiketleri (Entities)

| Etiket | Açıklama | Örnek |
|---|---|---|
| `BRAND` | Marka Adı | *Nike, Samsung, Enza Home, Pierre Cardin* |
| `CATEGORY` | Ürün Kategorisi / Türü | *Spor Ayakkabı, Akıllı Telefon, Masa Örtüsü* |
| `MODEL` | Model veya Ürün Serisi | *Air Max 270, Galaxy S24, Viyana* |
| `COLOR` | Renk Bilgisi | *Siyah, Uzay Grisi, Bej, Lacivert* |
| `SIZE_VARIANT` | Beden / Boyut / Kapasite | *42 Numara, XL, 150x220 cm, 128 GB* |
| `GENDER_TARGET` | Hedef Kitle | *Erkek, Kadın, Çocuk, Unisex* |
| `MATERIAL` | Malzeme / Kumaş Bileşimi | *Pamuk, Deri, Paslanmaz Çelik* |
| `SPECIFICATION` | Nitelik / Teknik Özellik | *Kareli, Kablosuz, Su Geçirmez, Mat Bitiş* |

## 📝 Örnek Veri Formatı

```json
{sample_json}
```

## 🚀 Kullanım (Hugging Face Datasets)

```python
from datasets import load_dataset

dataset = load_dataset("{repo_id}")
print(dataset["train"][0])
```

## 🛠️ Üretim Detayları

- **Üretici Araç**: NVIDIA NeMo Data Designer (`data-designer`)
- **LLM Model**: `deepseek-ai/DeepSeek-V4-Flash:fireworks-ai`
- **Ofset Doğrulaması**: Karakter başlangıç (`start`) ve bitiş (`end`) konumları tam eşleşme garantili hesaplanmıştır.
"""
    return readme_content


def main():
    parser = argparse.ArgumentParser(description="Push E-Commerce NER dataset to Hugging Face Hub")
    parser.add_argument("--repo-id", type=str, default=None, help="Hugging Face repo ID (e.g. username/turkish-ecommerce-ner-dataset)")
    parser.add_argument("--data-file", type=str, default=str(Path(__file__).parent / "data" / "ecommerce_ner_dataset.jsonl"), help="Path to .jsonl file")
    parser.add_argument("--private", action="store_true", help="Make repository private")
    args = parser.parse_args()

    token = os.getenv("HF_TOKEN")
    if not token or token == "hf_your_token_here":
        print("\n[ERROR] HF_TOKEN is missing or contains placeholder in .env file.")
        print("Lütfen .env dosyasındaki HF_TOKEN değerinizi kontrol edin.\n")
        sys.exit(1)

    api = HfApi(token=token)

    repo_id = args.repo_id
    if not repo_id:
        try:
            user_info = api.whoami()
            username = user_info.get("name")
            if username:
                repo_id = f"{username}/turkish-ecommerce-ner-dataset"
                print(f"[INFO] Auto-detected Hugging Face username: '{username}' -> Target Repo: '{repo_id}'")
        except Exception as e:
            print(f"[WARNING] Could not auto-detect HF username: {e}")

    if not repo_id:
        print("[ERROR] Please provide --repo-id username/dataset-name")
        sys.exit(1)

    data_path = Path(args.data_file)
    if not data_path.exists():
        print(f"[ERROR] Data file {data_path} not found. Please run generate_ecommerce_ner.py first.")
        sys.exit(1)

    # Count records and extract sample
    records = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    sample_rec = records[0] if records else {}
    total_count = len(records)

    print(f"[INFO] Prepared dataset: {total_count} records from {data_path}")

    # Generate README.md content
    readme_str = generate_dataset_card_readme(repo_id, sample_rec, total_count)
    readme_path = data_path.parent / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_str)

    print(f"[INFO] Created dataset README card at {readme_path}")

    print(f"[INFO] Creating/verifying Hugging Face repository '{repo_id}'...")
    create_repo(repo_id=repo_id, repo_type="dataset", private=args.private, exist_ok=True, token=token)

    print(f"[INFO] Uploading dataset file and README to {repo_id}...")
    api.upload_file(
        path_or_fileobj=str(data_path),
        path_in_repo="train.jsonl",
        repo_id=repo_id,
        repo_type="dataset",
    )
    api.upload_file(
        path_or_fileobj=str(readme_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
    )

    print(f"\n[SUCCESS] Dataset successfully published at: https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    main()
