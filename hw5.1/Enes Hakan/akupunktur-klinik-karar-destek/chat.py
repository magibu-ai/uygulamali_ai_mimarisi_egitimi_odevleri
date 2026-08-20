"""Ollama tabanli Turkce akupunktur klinik karar destek asistani."""

import os
import re

import requests

import rag
import tools

MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
MAX_TOOL_ROUNDS = 6
SYSTEM_PROMPT = """Sen hekimlere yardımcı olan Türkçe bir TCM klinik karar destek asistanısın.

Kurallar:
1. Kesin tanı veya tedavi emri verme; olası TCM paternlerini ve nokta adaylarını sırala. Son karar hekimindir.
2. Vaka için kitapta_ara aracını TAM BİR KEZ çağır. Sorguyu kısa ve İngilizce yaz; sonrasında bu aracı tekrar çağırma.
3. Kaynaklardan en fazla 2 nokta adayı seç. Her biri için nokta_bilgisi_getir aracını çağır; doğrulanmayan noktayı önerme.
4. Nokta aracı sonuçlarından sonra başka araç çağırmadan nihai yanıtı yaz.
5. Yalnızca araçların döndürdüğü kitap parçalarını kullan. Bilgi yetmiyorsa hangi bulgunun eksik olduğunu sor.
6. Çıktıyı şu başlıklarla kısa yaz: Olası TCM paterni, Gerekçe, Nokta adayları, Kaynaklar.
7. Kaynaklarda kitap sayfasını, PDF sayfasını ve page_image dosya yolunu belirt.
8. Modern tıbbi tanı yerine geçmediğini tek cümleyle hatırlat.
"""


def normalize_point(code: str) -> str:
    code = code.upper().replace("LIV-", "LV-").replace("DU-", "GV-")
    return code.replace("L.I.-", "LI-").replace("G.B.-", "GB-")


def ollama_chat(messages: list[dict], allow_tools: bool = True) -> dict:
    payload = {
        "model": MODEL, "messages": messages, "stream": False, "think": False,
        "options": {"temperature": 0, "num_predict": 300, "repeat_penalty": 1.2},
    }
    if allow_tools:
        payload["tools"] = tools.TOOL_SCHEMAS
    try:
        response = requests.post(
            f"{rag.OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=600,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama sohbet hatasi: {exc}") from exc
    return response.json()["message"]


def collect_case() -> str:
    fields = (
        ("Ana şikâyet ve süre", True), ("Dil bulgusu", False),
        ("Nabız bulgusu", False), ("Diğer önemli bulgular / mevcut tanılar", False),
        ("Ek not", False),
    )
    values = []
    for label, required in fields:
        while True:
            value = input(f"{label}: ").strip()
            if value or not required:
                values.append(f"{label}: {value or 'belirtilmedi'}")
                break
            print("Bu alan boş bırakılamaz.")
    return "\n".join(values)


def final_answer(messages: list[dict], checked_points: set[str]) -> str:
    allowed = ", ".join(sorted(checked_points))
    sources = "\n\n".join(m["content"] for m in messages if m["role"] == "tool")
    final = ollama_chat([
        {"role": "system", "content": (
            "Türkçe TCM klinik karar destek özeti yaz. Yalnızca verilen kaynakları kullan. "
            "Başlıklar: Olası TCM paterni, Gerekçe, Nokta adayları, Kaynaklar. "
            "Kesin tanı deme; son kararın hekimde olduğunu belirt. Kısa ol."
        )},
        {"role": "user", "content": (
            f"VAKA:\n{messages[1]['content']}\n\nDOĞRULANMIŞ NOKTALAR: {allowed}\n"
            f"Başka nokta adı/kodu yazma.\n\nKAYNAKLAR:\n{sources}"
        )},
    ], allow_tools=False)
    text = (final.get("content") or "Yanıt üretilemedi.").strip()
    mentioned = {normalize_point(code) for code in re.findall(r"\b[A-Z]{1,4}-\d+\b", text)}
    extra = mentioned - checked_points
    if extra and len(checked_points) < 2:
        code = sorted(extra)[0]
        result = tools.nokta_bilgisi_getir(code)
        if '"error"' not in result:
            checked_points.add(code)
            messages.append({"role": "tool", "tool_name": "nokta_bilgisi_getir", "content": result})
            print(f"  [araç] nokta_bilgisi_getir({{'nokta_kodu': '{code}'}}) [çıktı doğrulaması]")
            return final_answer(messages, checked_points)
    if extra:
        return "Yanıt güvenli üretilemedi: model doğrulanmamış bir nokta ekledi. Vakayı yeniden deneyin."
    return text


def answer(case: str) -> str:
    if tools.kirmizi_bayrak_var(case):
        return ("ACİL/KIRMIZI BAYRAK: Bu bulgular acil modern tıbbi değerlendirme gerektirebilir. "
                "Akupunktur noktası önerilmedi; yerel acil yardım sürecini başlatın.")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": case}]
    searched = False
    checked_points: set[str] = set()
    for _ in range(MAX_TOOL_ROUNDS):
        if len(checked_points) >= 2:
            return final_answer(messages, checked_points)
        allow_tools = True
        message = ollama_chat(messages, allow_tools=allow_tools)
        messages.append(message)
        calls = message.get("tool_calls") or []
        if not calls:
            if checked_points:
                return final_answer(messages, checked_points)
            return (message.get("content") or "Yanıt üretilemedi.").strip()
        for call in calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments") or {}
            function = tools.TOOLS.get(name)
            if name == "kitapta_ara" and searched:
                output = "Bu vaka için kitap araması zaten yapıldı; mevcut kaynaklarla nihai yanıtı yaz."
            elif name == "nokta_bilgisi_getir" and normalize_point(arguments.get("nokta_kodu", "")) in checked_points:
                output = "Bu nokta zaten doğrulandı; tekrar çağırma."
            try:
                if 'output' not in locals():
                    output = function(**arguments) if function else "Araç bulunamadı."
            except Exception as exc:
                output = f"Araç hatası: {exc}"
            searched |= name == "kitapta_ara"
            if name == "nokta_bilgisi_getir" and arguments.get("nokta_kodu"):
                checked_points.add(normalize_point(arguments["nokta_kodu"]))
            print(f"  [araç] {name}({arguments})")
            messages.append({"role": "tool", "tool_name": name, "content": output})
            del output
    return "Araç çağrı sınırına ulaşıldı; daha dar bir vaka sorgusu deneyin."


if __name__ == "__main__":
    print(f"Akupunktur Klinik Karar Destek — {MODEL}\nÇıkış: Ctrl+C\n")
    try:
        while True:
            print("\nYeni vaka")
            print("\nAsistan:\n" + answer(collect_case()))
    except (KeyboardInterrupt, EOFError):
        print("\nÇıkıldı.")
