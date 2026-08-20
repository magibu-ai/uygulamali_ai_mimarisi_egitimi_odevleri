"""
Terminal arayüzü.

Kullanım:
    python main.py              # sohbet
    python main.py --quiet      # araç çağrılarını gizle
    python main.py "soru"       # tek soru sor, cevabı bas, çık
"""

from __future__ import annotations

import sys

from agent import Agent
from config import BASE_URL, MODEL
from tools import TOOL_SCHEMAS

BANNER = f"""
╭──────────────────────────────────────────────────────────╮
│  🤖 Yerel Asistan — genel amaçlı, tool calling'li         │
╰──────────────────────────────────────────────────────────╯
  Model    : {MODEL}
  Sunucu   : {BASE_URL}
  Araçlar  : {len(TOOL_SCHEMAS)} adet ({", ".join(s["function"]["name"] for s in TOOL_SCHEMAS)})

  Komutlar : /araclar  araç listesi
             /sifirla  konuşma geçmişini temizle
             /cikis    çık
"""

COMMANDS = {"/cikis", "/çıkış", "/exit", "/quit", "q"}


def print_tools() -> None:
    print()
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        print(f"  • {fn['name']}")
        print(f"      {fn['description']}")
    print()


def main() -> None:
    args = [a for a in sys.argv[1:] if a not in ("--quiet", "-q")]
    verbose = "--quiet" not in sys.argv and "-q" not in sys.argv

    agent = Agent(verbose=verbose)

    # Tek seferlik soru modu — betikten çağırmak için.
    if args:
        print(agent.ask(" ".join(args)))
        return

    print(BANNER)
    while True:
        try:
            user_input = input("👤 Sen: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Görüşmek üzere.")
            return

        if not user_input:
            continue
        if user_input.lower() in COMMANDS:
            print("👋 Görüşmek üzere.")
            return
        if user_input.lower() in ("/araclar", "/araçlar", "/tools"):
            print_tools()
            continue
        if user_input.lower() in ("/sifirla", "/sıfırla", "/reset"):
            agent.reset()
            print("🧹 Geçmiş temizlendi.\n")
            continue

        print()
        answer = agent.ask(user_input)
        print(f"\n🤖 Asistan: {answer}\n")


if __name__ == "__main__":
    main()
