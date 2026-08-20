"""LLM katmanı: OpenAI-uyumlu istemci + tool-calling döngüsü.

Provider-agnostiktir: Groq, OpenAI, HF router, yerel vLLM/TGI — hepsi aynı
OpenAI Chat Completions arayüzünü konuştuğu için tek kod yolu yeterlidir.

Tool-calling döngüsü:
  1. Model, mesaj geçmişi + tool tanımlarıyla çağrılır.
  2. Model bir tool çağrısı isterse (tool_calls), ilgili Python fonksiyonu
     registry üzerinden çalıştırılır ve sonucu `role="tool"` mesajı olarak
     geçmişe eklenir.
  3. Model artık tool çağırmadığında (düz metin yanıt) döngü biter.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from .config import LLMConfig
from .schemas import TOOL_REGISTRY, TOOL_SCHEMAS

# Sonsuz döngüye karşı güvenlik sınırı.
MAX_TOOL_TURNS = 6


def _make_client(cfg: LLMConfig):
    """İstemciyi yapılandırmaya göre oluşturur.

    Mock modda (API anahtarı yok ya da LLM_BACKEND=mock) yerel kural tabanlı
    istemci; aksi halde OpenAI-uyumlu gerçek istemci döner. Her iki istemci de
    aynı `chat.completions.create(...)` arayüzünü sunar, döngü değişmez.
    """
    if cfg.use_mock:
        from .mock_llm import MockClient

        return MockClient()

    from openai import OpenAI  # kurulu değilse sadece bu yolda hata verir

    return OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)


def execute_tool_call(name: str, arguments: dict[str, Any]) -> Any:
    """Registry'den tool fonksiyonunu bulur ve çalıştırır."""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": "unknown_tool", "tool": name}
    try:
        return func(**arguments)
    except TypeError as exc:  # hatalı/eksik argüman
        return {"error": "bad_arguments", "detail": str(exc)}


def run_tool_loop(
    messages: list[dict[str, Any]],
    cfg: LLMConfig,
    on_tool_call: Optional[Callable[[dict[str, Any]], None]] = None,
    max_turns: int = MAX_TOOL_TURNS,
) -> tuple[str, list[dict[str, Any]]]:
    """Tool-calling döngüsünü çalıştırır ve (final_metin, tool_izi) döndürür.

    Args:
        messages: OpenAI formatında mesaj listesi (system + kullanıcı geçmişi).
        cfg: LLM yapılandırması.
        on_tool_call: Her tool çağrısında canlı bildirim için opsiyonel callback
            (ör. Gradio panelini anlık güncellemek için).
        max_turns: En fazla kaç tool turu (güvenlik sınırı).

    Returns:
        (asistanın son metin yanıtı, [ {name, arguments, result}, ... ])
    """
    client = _make_client(cfg)
    working = list(messages)  # orijinali bozmadan üzerinde çalış
    tool_trace: list[dict[str, Any]] = []

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=cfg.model,
            messages=working,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,  # kararlı, uydurmaya kapalı yanıtlar
        )
        msg = response.choices[0].message

        # Model tool çağırmadıysa: düz metin yanıt, döngü biter.
        if not msg.tool_calls:
            return (msg.content or "", tool_trace)

        # Asistanın tool_calls içeren mesajını geçmişe ekle.
        working.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        # Her tool çağrısını çalıştır ve sonucu geri besle.
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            result = execute_tool_call(name, args)
            record = {"name": name, "arguments": args, "result": result}
            tool_trace.append(record)
            if on_tool_call is not None:
                on_tool_call(record)

            working.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    # Tur sınırına ulaşıldı: son bir kez tool'suz özet iste.
    final = client.chat.completions.create(
        model=cfg.model,
        messages=working,
        temperature=0.2,
    )
    return (final.choices[0].message.content or "", tool_trace)
