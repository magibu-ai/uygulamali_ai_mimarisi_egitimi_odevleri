"""Araç çağırabilen kampüs asistanı (komut satırı)."""

import argparse
import ollama_client
import tools

MAX_TOOL_ROUNDS = 5  # sonsuz araç döngüsüne karşı emniyet freni

SYSTEM_PROMPT = """Sen Gazi Üniversitesi öğrencileri için geliştirilmiş, yetenekli bir kampüs asistanısın. Elinde 3 araç var:

- get_daily_menu  : Yemekhane menüsünü getirmek için (HTML_DOZER altyapısı ile).
- get_weather     : Kampüs ve çevresi hava durumu için.
- internet_search : Akademik takvim, üniversite duyuruları ve genel aramalar için.

EN ÖNEMLİ KURAL: Yemekhane menüsü veya duyuru sorulduğunda kesinlikle kendi bilgini uydurma (halüsinasyon yasak). Sadece araçlardan dönen veriyi kullanarak cevap ver. Veritabanı referanslarını (document_id) kullanıcıya doğrudan söyleme, sadece yemek listesini sıcak ve dostane bir dille aktar."""

parser = argparse.ArgumentParser(description="Ollama Tabanlı Kampüs Asistanı")
parser.add_argument("--chat-model", default=ollama_client.CHAT_MODEL, help="Ollama sohbet modeli")
args = parser.parse_args()

def run_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Modelin istediği araçları çalıştırır ve sonuçları mesaj formatında döndürür."""
    messages = []
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"].get("arguments") or {}
        print(f"  ⚙️ Çalıştırılıyor: {name}({arguments})")

        function = tools.TOOLS.get(name)
        if function is None:
            output = f"'{name}' adında bir araç yok."
        else:
            try:
                output = function(**arguments)
            except Exception as exc:  
                output = f"Araç çalıştırılamadı: {exc}"

        messages.append({"role": "tool", "tool_name": name, "content": output})
    return messages

print(" Kampüs / Yemekhane Asistanı Başlatıldı")
print(f"  Sohbet Modeli : {args.chat_model}")
print("  Çıkmak için   : cik\n")

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

while True:
    try:
        question = input("Öğrenci > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        break
    if not question:
        continue
    if question.lower() in {"cik", "çık", "exit", "quit"}:
        break

    messages.append({"role": "user", "content": question})

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            message = ollama_client.chat(
                messages, model=args.chat_model, tools=tools.TOOL_SCHEMAS
            )
            messages.append(message)
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                break
            messages.extend(run_tool_calls(tool_calls))
    except RuntimeError as exc:
        print(f"\nHata: {exc}\n")
        continue

    print(f"\nAsistan > {(message.get('content') or '').strip()}\n")
