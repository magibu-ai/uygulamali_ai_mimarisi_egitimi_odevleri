import argparse

import ollama_client
import tools


MAX_TOOL_ROUNDS = 5


SYSTEM_PROMPT = """
Sen KampüsGPT adında Türkçe konuşan bir üniversite öğrenci asistanısın.

Görevin öğrencilerin derslerle ve üniversite hayatıyla ilgili
basit sorularına yardımcı olmaktır.

Elinde iki araç vardır:

1. grade_calculator
   Öğrencinin vize-final ortalamasını veya geçmek için
   gereken final notunu hesaplar.

2. internet_search
   İnternetten güncel bilgi veya kaynak araştırır.

KURALLAR:

- Kullanıcı not, vize, final veya ders ortalaması hesabı
  istiyorsa MUTLAKA grade_calculator aracını kullan.

- Matematiksel not hesabını kendin yapma.

- Kullanıcı güncel bilgi, internet araştırması veya kaynak
  isterse internet_search aracını kullan.

- Kullanıcı sadece genel bir soru soruyorsa ve güncel
  bilgi gerekmiyorsa araç kullanmak zorunda değilsin.

- Selamlaşma gibi basit mesajlarda araç kullanma.

- Araçların döndürmediği bilgileri uydurma.

- Cevaplarını Türkçe, kısa ve anlaşılır şekilde ver.
"""


parser = argparse.ArgumentParser(
    description="KampüsGPT - Ollama tabanlı öğrenci asistanı"
)

parser.add_argument(
    "--chat-model",
    default=ollama_client.CHAT_MODEL,
    help="Kullanılacak Ollama modeli"
)

args = parser.parse_args()


def run_tool_calls(tool_calls: list[dict]) -> list[dict]:
    messages = []

    for call in tool_calls:

        name = call["function"]["name"]

        arguments = (
            call["function"].get("arguments") or {}
        )

        print(f"🔧 {name}({arguments})")

        function = tools.TOOLS.get(name)

        if function is None:
            output = f"'{name}' adında bir araç bulunamadı."

        else:
            try:
                output = function(**arguments)

            except Exception as exc:
                output = (
                    f"Araç çalıştırılırken hata oluştu: {exc}"
                )

        messages.append(
            {
                "role": "tool",
                "tool_name": name,
                "content": output
            }
        )

    return messages


print("\n🎓 KampüsGPT")
print(f"Model: {args.chat_model}")
print("Çıkmak için: cik\n")


messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]


while True:

    try:
        question = input("Siz > ").strip()

    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not question:
        continue

    if question.lower() in {
        "cik",
        "çık",
        "exit",
        "quit"
    }:
        break

    messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    try:

        for _ in range(MAX_TOOL_ROUNDS):

            message = ollama_client.chat(
                messages,
                model=args.chat_model,
                tools=tools.TOOL_SCHEMAS
            )

            messages.append(message)

            tool_calls = message.get("tool_calls")

            if not tool_calls:
                break

            messages.extend(
                run_tool_calls(tool_calls)
            )

    except RuntimeError as exc:

        print(f"\nHata: {exc}\n")

        continue

    print(
        f"\nKampüsGPT > "
        f"{(message.get('content') or '').strip()}\n"
    )