#!/usr/bin/env python3
"""MIHENK public sample'ını HuggingFace Hub'a yükler.

Ön koşullar:
    pip install huggingface_hub
    huggingface-cli login        (veya HF_TOKEN ortam değişkeni)

Kullanım:
    python scripts/build_hf.py                 # public split'i tazele
    python scripts/upload_hf.py                 # varsayılan repoya yükle
    python scripts/upload_hf.py kullanici/depo  # farklı repoya yükle

Yalnızca huggingface/ klasörü (dataset card + public JSONL) yüklenir;
private holdout gönderilmez.
"""
from __future__ import annotations

import os
import sys

REPO_ID_DEFAULT = "gorkemergune/mihenk-benchmark"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HF_DIR = os.path.join(ROOT, "huggingface")


def main():
    repo_id = sys.argv[1] if len(sys.argv) > 1 else REPO_ID_DEFAULT
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("huggingface_hub kurulu değil. Önce: pip install huggingface_hub")

    if not os.path.isfile(os.path.join(HF_DIR, "data", "mihenk_public.jsonl")):
        sys.exit("huggingface/data/mihenk_public.jsonl yok. Önce: python scripts/build_hf.py")

    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=HF_DIR,
        commit_message="MIHENK v1.0 public sample (Faz 1 pilot)",
    )
    print(f"Yüklendi: https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    main()
