"""
demo_cli.py
-----------
Uctan uca akisi terminalde gosteren demo. Her kullanici mesaji icin
tetiklenen tool-call ve donen gercek veri loglanir.

Calistirma (API/GPU olmadan, offline):
    LLM_BACKEND=mock python -m scripts.demo_cli

Gercek model ile:
    LLM_BACKEND=hf HF_TOKEN=hf_xxx MODEL_ID=Qwen/Qwen2.5-7B-Instruct python -m scripts.demo_cli
"""

import os
os.environ.setdefault("LLM_BACKEND", "mock")

from src.database import init_db
from src.agent import chat


def log(msg):
    print("    " + msg)


def main():
    init_db()  # sema + seed
    print("=" * 64)
    print(" LEZZET KAFE — Tool-Calling Asistan Demo   (backend=%s)" % os.environ["LLM_BACKEND"])
    print("=" * 64)

    senaryo = [
        "Merhaba, tatli menusunde neler var?",
        "2 adet kunefe siparis etmek istiyorum.",
        "1 numarali siparisimin durumu ne?",
        "Bir tane uzay burgeri alabilir miyim?",   # menude YOK -> halusinasyon testi
    ]

    history = []
    for user_msg in senaryo:
        print(f"\n👤 KULLANICI: {user_msg}")
        history, answer = chat(history + [{"role": "user", "content": user_msg}], log=log)
        print(f"🤖 ASISTAN : {answer}")

    print("\n" + "=" * 64)
    print(" Demo bitti. (Son istek menude olmayan bir urundu; asistan uydurmadi.)")
    print("=" * 64)


if __name__ == "__main__":
    main()
