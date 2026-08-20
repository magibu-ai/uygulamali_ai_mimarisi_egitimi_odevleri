"""
Projeyi Hugging Face Static Space'e yükler.

Neden ayrı bir betik? HF, Space ayarlarını README.md'nin başındaki YAML
başlığından okur; GitHub ise aynı başlığı README'nin tepesinde çirkin bir
metadata tablosu olarak gösterir. Bu yüzden repodaki README.md YAML'sız
tutuluyor, başlık `hf_header.yaml` dosyasında duruyor ve yalnızca yükleme
sırasında README'nin başına ekleniyor.

Kullanım:
    export HF_TOKEN=...        # ya da ~/.zshrc içinde tanımlıysa otomatik
    python push_to_hf.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import shutil

from huggingface_hub import HfApi

KOK = os.path.dirname(os.path.abspath(__file__))
REPO_ID = os.getenv("HF_SPACE_REPO", "ssilistre/yerel-llm-asistan")

# Space'e gönderilecek dosyalar. Yerel geliştirme artıkları listede yok.
GONDERILECEKLER = [
    "index.html",
    "README.md",
    "TESLIM.md",
    "ODEV.md",
    "ornek_konusmalar.md",
    "requirements.txt",
    "config.py",
    "system_prompt.py",
    "tools.py",
    "agent.py",
    "main.py",
    "demo_konusmalar.py",
    "build_static.py",
    "push_to_hf.py",
    "app.py",
]


def readme_yaml_ile() -> str:
    """README gövdesinin başına HF YAML başlığını ekler."""
    with open(os.path.join(KOK, "hf_header.yaml"), encoding="utf-8") as fh:
        baslik = fh.read().strip()
    with open(os.path.join(KOK, "README.md"), encoding="utf-8") as fh:
        govde = fh.read().lstrip()
    return f"---\n{baslik}\n---\n\n{govde}"


def main() -> None:
    token = os.getenv("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN tanımlı değil. `export HF_TOKEN=...` ile ayarla.")

    # index.html'i her yüklemeden önce tazele.
    sys.path.insert(0, KOK)
    import build_static

    build_static.main()

    api = HfApi(token=token)
    api.create_repo(repo_id=REPO_ID, repo_type="space", space_sdk="static", exist_ok=True)

    # Dosyaları geçici bir dizine kopyala; README'yi YAML'lı sürümüyle değiştir.
    with tempfile.TemporaryDirectory() as gecici:
        for ad in GONDERILECEKLER:
            kaynak = os.path.join(KOK, ad)
            if not os.path.exists(kaynak):
                print(f"  atlandı (yok): {ad}")
                continue
            shutil.copy2(kaynak, os.path.join(gecici, ad))

        with open(os.path.join(gecici, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(readme_yaml_ile())

        commit = api.upload_folder(
            folder_path=gecici,
            repo_id=REPO_ID,
            repo_type="space",
            commit_message="Space içeriği güncellendi",
        )

    print(f"✅ Yüklendi: https://huggingface.co/spaces/{REPO_ID}")
    print(f"   commit: {commit.commit_url}")


if __name__ == "__main__":
    main()
