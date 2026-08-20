import argparse
import json
import sys
import os

# Windows terminalde UTF-8 zorla (emoji ve Türkçe karakterler için)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

import ollama_client
import tools as t

MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """Sen "GökPusula" adında, Türkçe konuşan bir amatör gökyüzü gözlem asistanısın.
Amacın: kullanıcının bu geceki/ileriki gözlemini planlamasına yardım etmek.

Elindeki araçlar:
- goksel_gorunurluk : ay evresi, ay/güneş doğuş-batış, karanlık başlangıcı ve
  görünür gezegenler. "Bu gece ne görünür", "ay hangi evrede", "gezegenler"
  gibi sorularda kullan. Şehir gerekli; verilmezse kullanıcıya sor.
- gozlem_kosullari  : gözlem için hava/bulut uygun mu (bulut oranına göre verdikt).
- get_weather       : genel hava durumu.
- internet_search   : güncel gök olayları — meteor yağmuru, tutulma, ISS geçişi.

Kurallar:
1. Araçların döndürdüğü saat, yükseklik ve yüzde değerlerini DEĞİŞTİRME; olduğu
   gibi aktar, kendi tahmini rakamını ekleme.
2. Gözlem önerirken hem gökyüzünü (goksel_gorunurluk) hem havayı
   (gozlem_kosullari) birlikte değerlendir: gökyüzü şahane olsa da bulut varsa
   gözlem olmaz.
3. Sakin, meraklı ve pratik bir dille kısa yanıt ver; gereksiz teknik jargondan kaçın.
4. Selamlaşma gibi basit mesajlarda araç çağırma."""


def run_tool_calls(tool_calls, messages):
    for tc in tool_calls:
        name = tc["function"]["name"]
        args = tc.get("function", {}).get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}

        arg_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
        print(f"  🔧 {name}({arg_str})")

        fn = t.TOOLS.get(name)
        if fn:
            try:
                result = fn(**args)
            except Exception as e:
                result = f"Araç hatası ({name}): {e}"
        else:
            result = f"Bilinmeyen araç: {name}"

        messages.append({
            "role": "tool",
            "name": name,
            "content": str(result),
        })
    return messages


def main():
    parser = argparse.ArgumentParser(description="GökPusula - Gökyüzü Gözlem Asistanı")
    parser.add_argument(
        "--chat-model",
        default=ollama_client.CHAT_MODEL,
        help="Ollama model adı (varsayılan: qwen2.5:7b-instruct)",
    )
    args = parser.parse_args()

    model = args.chat_model
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("=" * 60)
    print("  GökPusula — Yerel LLM Gökyüzü Gözlem Asistanı")
    print("  Model:", model)
    print("  Çıkmak için 'cik' yazın.")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("Siz: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGörüşürüz!")
            break

        if user_input.lower() == "cik":
            print("Görüşürüz! Bulutlarda kaybolmayın. ☽")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = ollama_client.chat(
                    messages=messages,
                    model=model,
                    tools=t.TOOL_SCHEMAS,
                )
            except RuntimeError as e:
                print(f"\nHata: {e}\n")
                messages.pop()
                break

            messages.append(response)

            if response.get("tool_calls"):
                messages = run_tool_calls(response["tool_calls"], messages)
            else:
                print(f"\nGökPusula: {response.get('content', '')}\n")
                break
        else:
            print("\nGökPusula: Araç çağrı sınırına ulaşıldı. Lütfen soruyu yeniden sorun.\n")


if __name__ == "__main__":
    main()
