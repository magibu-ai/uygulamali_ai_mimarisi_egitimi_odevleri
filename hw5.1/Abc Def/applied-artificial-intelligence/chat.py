"""Arac cagirabilen sohbet asistani (komut satiri).

Dongu cok basit:
    kullanici sorar -> model ya cevap verir ya da bir arac cagirir
                    -> araci biz calistirir, sonucu modele geri veririz
                    -> model nihai cevabi yazar

Kullanim:
    python3 chat.py
"""

import ollama_client
import tools

MAX_TOOL_ROUNDS = 5  # sonsuz arac dongusune karsi emniyet freni

MODEL = "qwen2.5"

SYSTEM_PROMPT = """Sen Türkçe konuşan yardımcı bir asistansın. Elinde şu araç var:

- get_pollen_status      : polen durumu

EN ÖNEMLİ KURAL: get_pollen_status aracının döndürdüğü metni AYNEN kullanıcıya aktar.
Üzerine kendi bilgini ekleme, cevabı genişletme, düzeltme veya yorumlama. Düşük veya yüksek gibi yorumlar üretme. 
Polen alerjileri ile ilgili yorum yapma. Risk ile ilgili yorum yapma. Polen seviyesi hakkında yorum yapma. Polen değerlerini yazdıktan sonra dur, başka çıktı üretme. 
Doktor ile ilgili yorum yapma. Sağlık konularında tavsiye verme. Herhangi bir öneride bulunma. Alerji ile ilgili çıktı üretme. get_pollen_status aracının döndürdüğü metnin sonuna ekleme yapma.
Eğer araç "Polen durumu alınamadı" diyorsa sen de sadece bunu söyle; alternatif bir açıklama üretme. Cevabını Türkçe kısa ve sade yaz. Türkçe dışındaki bir dilde herhangi bir şey yazma.
  
Selamlaşma ve sohbet gibi basit mesajlar için araç çağırmana gerek yok."""


def run_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Modelin istedigi araclari calistirir ve sonuclari mesaj formatinda dondurur."""
    messages = []
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"].get("arguments") or {}
        print(f"  🔧 {name}({arguments})")

        function = tools.TOOLS.get(name)
        if function is None:
            output = f"'{name}' adinda bir arac yok."
        else:
            try:
                output = function(**arguments)
            except Exception as exc:  # arac hatasi sohbeti bitirmesin
                output = f"Arac calistirilamadi: {exc}"

        messages.append({"role": "tool", "tool_name": name, "content": output})
    return messages


print("Ollama Polen Takibi")
print(f"  sohbet modeli   : {MODEL}")
print("  cikmak icin: cik\n")

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

while True:
    try:
        question = input("Siz > ").strip()
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
                messages, model=MODEL, tools=tools.TOOL_SCHEMAS
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
