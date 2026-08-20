"""
llm.py
------
Modelin cagirilmasi ve tool-call ciktisinin ayristirilmasi.

Backend secimi (LLM_BACKEND ortam degiskeni):
  * "auto" (VARSAYILAN) -> HF_TOKEN varsa gercek model ("hf"), yoksa "mock".
  * "hf"   -> Hugging Face Inference Providers (OpenAI-uyumlu, tools destekli).
              Kendi servis edilebilir modelinizi MODEL_ID ile verebilirsiniz.
  * "mock" -> API/GPU olmadan, deterministik kurallarla tool-call ureten
              offline test backend'i. (Bir dil modeli DEGILDIR; sadece demo/test.)

Cikti sozlesmesi (tum backend'ler ayni sekli dondurur):
    {"content": "<metin ya da bos>", "tool_calls": [{"name":..., "arguments":{...}}, ...]}
"""

import os
import re
import json

# Gated olmayan, tool-calling'i guclu varsayilan model.
MODEL_ID = os.environ.get("MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")

_RAW_BACKEND = os.environ.get("LLM_BACKEND", "auto").lower()
_HAS_TOKEN = bool(os.environ.get("HF_TOKEN"))

# Etkin backend'i coz (arayuz bunu dürüstçe gosterir)
if _RAW_BACKEND == "auto":
    ACTIVE_BACKEND = "hf" if _HAS_TOKEN else "mock"
else:
    ACTIVE_BACKEND = _RAW_BACKEND

# <tool_call>{...}</tool_call> bloklarini yakalayan regex (yerel modeller icin)
_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_tool_calls_from_text(text: str) -> dict:
    """Serbest metinden <tool_call> bloklarini cikarir (yerel/transformers yolu)."""
    calls = []
    for m in _TOOL_CALL_RE.finditer(text or ""):
        try:
            obj = json.loads(m.group(1))
            calls.append({"name": obj["name"], "arguments": obj.get("arguments", {})})
        except (json.JSONDecodeError, KeyError):
            continue
    clean = _TOOL_CALL_RE.sub("", text or "").strip()
    return {"content": clean, "tool_calls": calls}


# ---------------------------------------------------------------------------
# Backend 1: Hugging Face Inference Providers (gercek model)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    global _client
    if _client is None:
        from huggingface_hub import InferenceClient
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError(
                "HF_TOKEN tanimli degil. Gercek model icin bir Hugging Face WRITE/READ "
                "token'i ayarlayin (Space > Settings > Secrets > HF_TOKEN)."
            )
        # provider='auto' -> en uygun saglayiciya yonlendirir (router.huggingface.co)
        _client = InferenceClient(provider="auto", api_key=token)
    return _client


def _call_hf(messages: list, tools: list) -> dict:
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        max_tokens=512,
        temperature=0.2,
    )
    msg = resp.choices[0].message

    tool_calls = []
    for tc in (msg.tool_calls or []):
        args = tc.function.arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        tool_calls.append({"id": getattr(tc, "id", None), "name": tc.function.name, "arguments": args})

    content = msg.content or ""
    # Bazi modeller tool_call'u metin icinde dondurur -> yedek ayristirma
    if not tool_calls and "<tool_call>" in content:
        return parse_tool_calls_from_text(content)

    return {"content": content, "tool_calls": tool_calls}


# ---------------------------------------------------------------------------
# Backend 2: Offline mock (deterministik) — sadece test/demo icin
# ---------------------------------------------------------------------------
def _call_mock(messages: list, tools: list) -> dict:
    last_user = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"].lower()
            break

    last = messages[-1]
    if last["role"] == "tool":
        data = json.loads(last["content"]) if isinstance(last["content"], str) else last["content"]
        if "error" in data:
            return {"content": f"Uzgunum, {data['error']}", "tool_calls": []}
        if "items" in data and "order_id" not in data:
            names = ", ".join(f"{i['name']} ({i['price']} TL)" for i in data["items"])
            return {"content": f"Menude sunlar var: {names}.", "tool_calls": []}
        if "order_id" in data and "message" in data:
            return {"content": data["message"], "tool_calls": []}
        if "status" in data:
            return {"content": f"#{data['order_id']} numarali siparisin durumu: "
                               f"{data['status']} (toplam {data['total']} TL).", "tool_calls": []}
        return {"content": json.dumps(data, ensure_ascii=False), "tool_calls": []}

    if any(k in last_user for k in ["menu", "ne var", "tatli", "icecek", "yemek"]):
        cat = None
        for c in ["tatli", "icecek", "ana"]:
            if c in last_user:
                cat = c
        return {"content": "", "tool_calls": [{"name": "get_menu",
                "arguments": {"category": cat} if cat else {}}]}

    if any(k in last_user for k in ["durum", "nerede", "hazir mi", "siparisim"]):
        m = re.search(r"#?(\d+)", last_user)
        oid = int(m.group(1)) if m else 1
        return {"content": "", "tool_calls": [{"name": "check_order_status",
                "arguments": {"order_id": oid}}]}

    if any(k in last_user for k in ["siparis", "istiyorum", "alabilir", "ekle", "getir bana"]):
        qty = 1
        m = re.search(r"(\d+)\s*(adet|tane)?", last_user)
        if m:
            qty = int(m.group(1))
        item = None
        for known in ["kunefe", "baklava", "sutlac", "ayran", "limonata", "adana kebap",
                      "izgara kofte", "tavuk sote", "mercimek corbasi", "turk kahvesi"]:
            if known in last_user:
                item = known.title()
        if item is None:
            m2 = re.search(r"(?:bir tane|bir|\d+\s*(?:adet|tane)?)\s+([a-zcgiosu ]+?)"
                           r"(?:\s+(?:alabilir|istiyorum|siparis|ver|getir|ekle))",
                           last_user)
            item = (m2.group(1).strip().title() if m2 else last_user.strip().title())
        return {"content": "", "tool_calls": [{"name": "create_order",
                "arguments": {"customer": "Musteri", "items": [{"name": item, "quantity": qty}]}}]}

    return {"content": "Menu, siparis olusturma veya siparis durumu konularinda yardimci olabilirim.",
            "tool_calls": []}


def generate(messages: list, tools: list) -> dict:
    """Etkin backend'e gore model ciktisini uretir."""
    if ACTIVE_BACKEND == "mock":
        return _call_mock(messages, tools)
    return _call_hf(messages, tools)
