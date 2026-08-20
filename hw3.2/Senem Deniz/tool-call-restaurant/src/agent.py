"""
agent.py
--------
Sohbet dongusunu yoneten cekirdek.

Akis:
  1. Kullanici mesaji eklenir.
  2. Model cagirilir (llm.generate).
  3. Model tool_call dondurduyse -> TOOL_REGISTRY'den gercek fonksiyon calisir,
     sonuc "tool" roluyle gecmise eklenir ve model tekrar cagirilir.
  4. Model duz metin dondurunce yanit kullaniciya verilir.

Halusinasyon engelleme:
  - Model yalnizca TOOL_REGISTRY'de tanimli araclari cagirabilir; taninmayan
    arac cagrisi hata olarak modele geri doner.
  - Nihai cevaplar tool ciktisina dayanir; model uydursa bile veri katmani
    (tools.py) menude olmayan urun icin {"error": ...} dondurur.
"""

import json

from .tools import TOOL_REGISTRY
from .tool_schemas import TOOLS
from .llm import generate

MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = (
    "Sen 'Lezzet Kafe'nin Turkce konusan siparis asistanisin. "
    "Musterilere menu bilgisi verir, siparis olusturur ve siparis durumunu sorgularsin. "
    "Bir islem icin mutlaka ilgili araci cagir. Menude/veritabaninda olmayan bir urun "
    "veya bilgi hakkinda ASLA tahmin yurutme; sadece araclardan donen gercek veriyi kullan."
)


def _run_tool(name: str, arguments: dict) -> dict:
    """Tool adini gercek fonksiyona yonlendirir (guvenli sekilde)."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"Tanimsiz arac: {name}"}
    try:
        return fn(**(arguments or {}))
    except TypeError as e:
        return {"error": f"Gecersiz parametreler ({name}): {e}"}
    except Exception as e:  # veritabani vb. hatalar
        return {"error": f"Arac calisirken hata ({name}): {e}"}


def chat(history: list, log=None) -> tuple:
    """
    history: [{"role": "user"/"assistant"/..., "content": ...}, ...]
    log:     opsiyonel callable(str) -> terminal/log ciktisi icin.
    Donen:   (guncellenmis_history, asistan_metni)
    """
    def _log(msg):
        if log:
            log(msg)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for _ in range(MAX_TOOL_ROUNDS):
        result = generate(messages, TOOLS)
        tool_calls = result.get("tool_calls") or []

        if not tool_calls:
            answer = result.get("content", "").strip()
            messages.append({"role": "assistant", "content": answer})
            return messages[1:], answer  # system'i disari verme

        # Model bir/birden fazla arac cagirdi
        api_tool_calls = []
        for i, tc in enumerate(tool_calls):
            call_id = tc.get("id") or f"call_{i}"
            tc["_id"] = call_id
            args = tc["arguments"]
            args_str = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
            api_tool_calls.append({
                "id": call_id, "type": "function",
                "function": {"name": tc["name"], "arguments": args_str},
            })
        messages.append({"role": "assistant",
                         "content": result.get("content", "") or "",
                         "tool_calls": api_tool_calls})

        for tc in tool_calls:
            args = tc["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            _log(f"🔧 TOOL-CALL -> {tc['name']}({json.dumps(args, ensure_ascii=False)})")
            tool_result = _run_tool(tc["name"], args)
            _log(f"📦 TOOL-RESULT <- {json.dumps(tool_result, ensure_ascii=False)}")
            messages.append({"role": "tool", "tool_call_id": tc["_id"],
                             "name": tc["name"],
                             "content": json.dumps(tool_result, ensure_ascii=False)})

    # Guvenlik siniri
    answer = "Islem cok fazla adim gerektirdi, lutfen isteginizi sadelestirin."
    messages.append({"role": "assistant", "content": answer})
    return messages[1:], answer
