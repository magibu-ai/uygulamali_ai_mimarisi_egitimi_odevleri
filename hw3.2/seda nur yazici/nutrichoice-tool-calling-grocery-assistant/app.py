from __future__ import annotations

import os
import traceback
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv

from assistant.agent import NutriChoiceAgent
from database.initialize import initialize_database

load_dotenv()
initialize_database()

AGENT: NutriChoiceAgent | None = None


def get_agent() -> NutriChoiceAgent:
    global AGENT
    if AGENT is None:
        AGENT = NutriChoiceAgent.from_environment()
    return AGENT


def respond(
    message: str,
    history: list[dict],
    request: gr.Request | None = None,
) -> str:
    if not message.strip():
        return "Lütfen bir ürün arama veya alışveriş listesi isteği yazın."

    try:
        session_id = request.session_hash if request and request.session_hash else "default"
        return get_agent().chat(
            message,
            history,
            session_id=session_id,
        )
    except Exception as exc:
        traceback.print_exc()
        backend = os.getenv("MODEL_BACKEND", "rules").strip().lower()
        if backend == "transformers" and isinstance(exc, (ImportError, RuntimeError)):
            return (
                "Model backend'i başlatılamadı. `.env` dosyasında geçici olarak "
                "`MODEL_BACKEND=rules` kullanın veya model bağımlılıklarını kurun. "
                f"Teknik ayrıntı: {type(exc).__name__}: {exc}"
            )
        return f"İşlem sırasında hata oluştu: {type(exc).__name__}: {exc}"


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="NutriChoice") as demo:
        gr.Markdown(
            """
# 🛒 NutriChoice
### Grounded Tool-Calling Grocery Assistant

Open Food Facts verilerinden ürün arar, barkodla ürün ayrıntılarını doğrular ve alışveriş listenizi SQLite üzerinde yönetir.

**Desteklenen kapsam:** ürün arama, ürün detayı, listeye ekleme, kesin miktar ayarlama, miktar azaltma ve liste görüntüleme. Tarif veya serbest beslenme tavsiyesi üretimi bilinçli olarak kapsam dışıdır.
            """
        )
        gr.ChatInterface(
            fn=respond,
            examples=[
                "100 gramında en fazla 10 gram şeker olan kahvaltılık ürünleri bul.",
                "3229820019307 ve 3159470000120 barkodlu ürünlerin detayını getir.",
                "3159470000120 barkodlu ürünü alışveriş listeme ekle.",
                "Alışveriş listemi görüntüle.",
            ],
        )
        gr.Markdown(
            "Veri kaynağı: Open Food Facts. Ürün bilgileri topluluk tarafından sağlandığı için eksik veya hatalı olabilir."
        )
    return demo


if __name__ == "__main__":
    Path(os.getenv("DATABASE_PATH", "data/nutrichoice.db")).parent.mkdir(
        parents=True, exist_ok=True
    )
    build_demo().launch()
