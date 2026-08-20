"""Agent orkestrasyonu: sistem promptu, mesaj kurulumu ve yanıt üretimi.

Bu katman UI'dan (Gradio/CLI) bağımsızdır. Sohbet geçmişini alır, güçlü bir
anti-halüsinasyon sistem promptu ekler, LLM tool-calling döngüsünü çalıştırır
ve hem kullanıcıya gösterilecek metni hem de tetiklenen tool izini döndürür.
"""

from __future__ import annotations

from typing import Any, Optional

from .config import LLMConfig, get_llm_config
from .llm import run_tool_loop

# Anti-halüsinasyon sözleşmesi: model yalnızca tool çıktısına dayanır.
SYSTEM_PROMPT = """Sen "Cinema-AI"sın: bir film öneri ve izleme listesi asistanısın.

GÖREVİN:
- Kullanıcıya film önermek, film aramak ve izleme listelerini yönetmek.
- Bunları YALNIZCA sana verilen araçlar (tools) üzerinden yaparsın.

KESİN KURALLAR (halüsinasyon yasağı):
1. Film önerirken veya bilgi verirken SADECE araçlardan (search_movies,
   get_movie_details, get_watchlist) dönen gerçek veriyi kullan. Kendi
   hafızandan film ADI, PUANI, YÖNETMENİ veya YILI UYDURMA.
2. Bir filmi izleme listesine eklemeden önce mutlaka search_movies ile
   doğrula ve gerçek movie_id kullan.
3. Araç "not_found" veya boş sonuç döndürürse, bunu kullanıcıya dürüstçe
   söyle ("Veritabanımızda böyle bir film bulamadım") — asla var gibi davranma.
4. Puan, yıl, yönetmen gibi tüm detaylar araç çıktısındaki değerlerle birebir
   aynı olmalı.
5. Sıcak, doğal, arkadaşça bir Türkçe konuş; film seven gerçek bir dost gibi.
   "Size nasıl yardımcı olabilirim", "Tabii ki!", "Bir yapay zeka olarak" gibi
   klişe/robotik kalıplardan kaçın. Önerdiğin filmleri kısa madde listesiyle ver.

Kullanıcı bir tür/yıl/puan belirtirse önce search_movies çağır, sonuçları
özetle. "Listeme ekle" derse add_to_watchlist kullan. "Listemde ne var?"
derse get_watchlist kullan."""


def build_messages(
    history: list[dict[str, str]], user_message: Optional[str] = None
) -> list[dict[str, Any]]:
    """Sistem promptu + sohbet geçmişinden OpenAI mesaj listesi kurar.

    Args:
        history: [{"role": "user"|"assistant", "content": ...}, ...] biçiminde geçmiş.
        user_message: Verilirse sona yeni bir kullanıcı mesajı olarak eklenir.
    """
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history:
        role = turn.get("role")
        if role in ("user", "assistant") and turn.get("content"):
            messages.append({"role": role, "content": turn["content"]})
    if user_message:
        messages.append({"role": "user", "content": user_message})
    return messages


def respond(
    history: list[dict[str, str]],
    user_message: Optional[str] = None,
    cfg: Optional[LLMConfig] = None,
    on_tool_call=None,
) -> tuple[str, list[dict[str, Any]]]:
    """Kullanıcının son mesajına yanıt üretir.

    Returns:
        (asistan_metni, tool_izi). tool_izi her adım için
        {name, arguments, result} kayıtları içerir; UI panelinde gösterilir.
    """
    cfg = cfg or get_llm_config()
    if not cfg.is_ready:
        raise RuntimeError(
            "LLM_API_KEY tanımlı değil. .env dosyanıza Groq API anahtarınızı ekleyin "
            "(bkz. .env.example)."
        )
    messages = build_messages(history, user_message)
    return run_tool_loop(messages, cfg, on_tool_call=on_tool_call)
