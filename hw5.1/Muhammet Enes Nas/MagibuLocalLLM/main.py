"""Arac cagirabilen finans sohbet asistani (komut satiri).

Dongu cok basit:
    kullanici sorar -> model ya cevap verir ya da bir arac cagirir
                    -> araci biz calistiririz, sonucu modele geri veririz
                    -> model nihai cevabi yazar

Kullanim:
    python main.py
    python main.py --chat-model qwen3:1.7b
    python main.py --embed-model gemma        # bilgi bankasi aramasini degistir
"""

import argparse
import itertools
import sys
import threading
import time

import config
import ollama_client
import tools
from system_prompt import FEW_SHOT_MESSAGES, SYSTEM_PROMPT

CYAN, GREEN, YELLOW, GREY, RED, RESET = (
    "\033[1;36m", "\033[1;32m", "\033[33m", "\033[90m", "\033[31m", "\033[0m",
)


class Spinner:
    """Model dusunurken gecen sureyi gosterir.

    Neden gerekli? Model bir cevabi 3 saniyede de 60 saniyede de uretebilir ve
    bu sure boyunca ekranda hicbir sey olmaz. Kullanici programin donduguyla
    calistigini ayirt edemez. Gecen saniyeyi gostermek bu belirsizligi kaldirir.
    """

    def __init__(self, label: str):
        self.label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def _spin(self):
        frames = itertools.cycle("|/-\\")
        started = time.time()
        while not self._stop.wait(0.15):
            elapsed = time.time() - started
            # 20 saniyeyi asarsa renk degistir: "bir terslik olabilir" sinyali.
            color = YELLOW if elapsed > 20 else GREY
            sys.stdout.write(f"\r  {color}{next(frames)} {self.label}... {elapsed:.0f}s{RESET}  ")
            sys.stdout.flush()

    def __exit__(self, *_exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        sys.stdout.write("\r" + " " * 60 + "\r")  # satiri temizle
        sys.stdout.flush()


def parse_args():
    parser = argparse.ArgumentParser(description="Ollama tabanli finans arastirma asistani.")
    parser.add_argument("--chat-model", default=config.CHAT_MODEL, help="Ollama sohbet modeli")
    parser.add_argument(
        "--embed-model",
        default=config.EMBED_MODEL,
        choices=list(ollama_client.EMBED_MODELS),
        help="Bilgi bankasi aramasinda kullanilacak embedding modeli",
    )
    parser.add_argument(
        "--few-shot",
        action="store_true",
        help="Few-shot ornekleri ekle (VARSAYILAN KAPALI — qwen3:0.6b'de geri tepti, "
             "model araci atlayip cevap bicimini taklit ederek sayi uydurdu)",
    )
    return parser.parse_args()


def run_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Modelin istedigi araclari calistirir ve sonuclari mesaj formatinda dondurur."""
    messages = []
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"].get("arguments") or {}
        print(f"  {YELLOW}🔧 {name}({arguments}){RESET}")

        function = tools.TOOLS.get(name)
        if function is None:
            output = f"'{name}' adinda bir arac yok. Kullanilabilir araclar: {list(tools.TOOLS)}"
        else:
            try:
                with Spinner(f"{name} calisiyor"):
                    output = function(**arguments)
            except TypeError as exc:
                # Model parametreleri yanlis verdi; duzeltebilmesi icin sebebi geri bildir.
                output = f"Arac parametreleri hatali: {exc}"
            except Exception as exc:  # arac hatasi sohbeti bitirmesin
                output = f"Arac calistirilamadi: {exc}"

        preview = output.replace("\n", " ")
        print(f"  {GREY}   → {preview[:180]}{'...' if len(preview) > 180 else ''}{RESET}")
        messages.append({"role": "tool", "tool_name": name, "content": output})
    return messages


def main():
    args = parse_args()
    tools.ACTIVE_EMBED_KEY = args.embed_model

    print(f"{CYAN}{'=' * 58}")
    print("  💰 FinansBot — Kisisel Finans & Yatirim Arastirma Asistani")
    print(f"{'=' * 58}{RESET}")
    print(f"  Sohbet modeli   : {args.chat_model}")
    print(f"  Embedding modeli: {ollama_client.EMBED_MODELS[args.embed_model]['name']}")
    print(f"  Araclar         : {', '.join(tools.TOOLS)}")
    print(f"  Web aramasi     : {'Tavily' if config.TAVILY_API_KEY else 'DuckDuckGo (TAVILY_API_KEY bos)'}")
    print(f"  {GREY}Cikmak icin: cik / exit / quit   |   Soruyu iptal: Ctrl+C{RESET}")
    print()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if args.few_shot:
        messages += list(FEW_SHOT_MESSAGES)

    while True:
        try:
            question = input(f"{GREEN}Siz > {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Gorusmek uzere!{RESET}")
            break
        if not question:
            continue
        if question.lower() in {"cik", "çık", "exit", "quit"}:
            print(f"{YELLOW}Gorusmek uzere!{RESET}")
            break

        # Iptal ya da hata durumunda gecmisi bu noktaya geri sarabilmek icin
        # isaretliyoruz. Yarim kalmis bir tur gecmiste kalirsa sonraki cevaplari bozar.
        checkpoint = len(messages)
        messages.append({"role": "user", "content": question})

        message = {}
        try:
            for _ in range(config.MAX_TOOL_ROUNDS):
                with Spinner("dusunuyor"):
                    message = ollama_client.chat(
                        messages, model=args.chat_model, tools=tools.TOOL_SCHEMAS
                    )
                messages.append(message)
                tool_calls = message.get("tool_calls")
                if not tool_calls:
                    break
                messages.extend(run_tool_calls(tool_calls))
            else:
                # Dongu arac cagirmakla bitti: model hala arac istiyor ama sinira geldik.
                # Elimizdeki arac sonuclariyla nihai cevabi yazmasini istiyoruz.
                messages.append(
                    {
                        "role": "user",
                        "content": "Yeterli veri toplandi. Baska arac cagirma, simdi cevabi yaz.",
                    }
                )
                with Spinner("cevap yaziliyor"):
                    message = ollama_client.chat(messages, model=args.chat_model)
                messages.append(message)

        except KeyboardInterrupt:
            # Ctrl+C programi kapatmasin, sadece bu soruyu iptal etsin.
            del messages[checkpoint:]
            print(f"\n{YELLOW}Soru iptal edildi. Yeni soru sorabilirsiniz.{RESET}\n")
            continue
        except RuntimeError as exc:
            del messages[checkpoint:]
            print(f"\n{RED}Hata: {exc}{RESET}")
            print(f"{GREY}Sohbet gecmisi bu soru oncesine geri alindi.{RESET}\n")
            continue

        answer = (message.get("content") or "").strip()
        if answer:
            print(f"\n{CYAN}FinansBot > {RESET}{answer}\n")
        else:
            # Arac cagirdi ama metin uretmedi ya da uretim tavana takildi.
            print(f"\n{CYAN}FinansBot > {RESET}{YELLOW}(Model metin uretmedi.){RESET}")
            print(f"{GREY}Soruyu daha kisa ve net sorun, ya da daha buyuk bir model deneyin:")
            print(f"  python main.py --chat-model qwen3:1.7b{RESET}\n")


if __name__ == "__main__":
    main()
