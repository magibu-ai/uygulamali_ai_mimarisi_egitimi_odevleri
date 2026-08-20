"""
Veri setini Hugging Face Hub'a yükler.

Ön koşul: `huggingface-cli login` ile giriş yapmis ya da HF_TOKEN ortam
degiskeni ayarlanmis olmali (write yetkili token).

Kullanim:
    uv run python push_to_hub.py --repo <kullanici>/giresun_kultur
    uv run python push_to_hub.py --repo <kullanici>/giresun_kultur --private
"""

import argparse
from build_dataset import build


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Hub repo id, or. kullanici/giresun_kultur")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()

    ds = build()
    ds.push_to_hub(args.repo, private=args.private)
    print(f"Push tamam: https://huggingface.co/datasets/{args.repo}")


if __name__ == "__main__":
    main()