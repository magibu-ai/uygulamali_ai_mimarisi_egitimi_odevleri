"""Otomotiv yaris asistani: arac cagirabilen sohbet (komut satiri).

Dongu cok basit:
    kullanici sorar -> model ya cevap verir ya da bir arac cagirir
                    -> araci biz calistirir, sonucu modele geri veririz
                    -> model nihai cevabi yazar (gerekirse birden fazla arac)

Kullanim:
    python chat.py
    python chat.py --chat-model qwen2.5:7b-instruct
"""

import argparse
import sys

import ollama_client
import tools

# Windows konsolu varsayilan olarak cp1254 kullanabilir; emoji/UTF-8 karakterler
# aksi halde UnicodeEncodeError ile cokebilir. Ciktiyi UTF-8'e sabitle.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

MAX_TOOL_ROUNDS = 5  # sonsuz arac dongusune karsi emniyet freni

SYSTEM_PROMPT = """Sen "Otomotiv Yaris Asistani"sin: bir universite yaris takimina
yardim eden, Turkce konusan bir asistansin.

SENARYO
Takim; yaris hazirligi, arac bakimi, bilesen durumu, hava kosullari ve yaris
yonetmelikleri konularinda sana danisir. Arac verileri ve yonetmelikler GERCEK
DEGIL, akademik bir projeye ait GOSTERIM (DEMO) verileridir.

ELINDEKI 4 ARAC
- get_weather(city)            : bir sehrin GUNCEL, canli hava durumu.
- check_part_status(component) : bir arac bileseninin DEMO durumu
                                 (fren balatalari, fren diskleri, lastikler,
                                  motor yagi, aku).
- get_race_regulations(topic)  : bir yaris yonetmeligi konusunun DEMO ozeti
                                 (frenler, lastikler, guvenlik, elektrik,
                                  surucu, teknik muayene).
- internet_search(query)       : guncel/harici bilgi ya da acik web aramasi.

ARAC SECIM KURALLARI
- Hava, sicaklik, yagmur, ruzgar, yaris/antrenman gunu havasi  -> get_weather
- Bilesen durumu/bakim/muayene/kalan omur/uyari                -> check_part_status
- Yaris ya da teknik yonetmelik/kural                          -> get_race_regulations
- Guncel/harici bilgi, haber ya da acik web aramasi istegi     -> internet_search
- internet_search'i, hava/bilesen/yonetmelik gibi ozel bir aracin zaten
  karsiladigi bilgi icin KULLANMA.

ARAC KULLANMA
Selamlasma, tesekkur ve dogrudan cevaplanabilen genel sorular icin arac cagirma.
Gereksiz arac cagirma; bir arac gerekmiyorsa dogrudan yanit ver.

COKLU ARAC
Bir soru birden fazla BAGIMSIZ bilgi gerektiriyorsa araclari SIRAYLA cagir. Ornek:
"Yarin yagmur varsa fren balatalarini kontrol etmeli miyiz?" -> once get_weather,
sonra check_part_status, sonra iki sonucu birlestirip cevap ver.

ARAC SONUCLARINI KULLANMA
- Cevabini yalnizca gercekten donen arac sonuclarina dayandir.
- Bir araci cagirmadiysan onu kullanmis gibi yapma.
- Arac sonuclarini uydurma; sonuc yoksa ya da bilgi mevcut degilse bunu acikca soyle.
- Ham JSON'u ya da arac cagirma metnini kullaniciya gosterme; sonucu sade Turkce ozetle.

DEMO VERI SINIRI
check_part_status ve get_race_regulations verileri DEMO'dur; gercek telemetri,
gercek sensor ya da resmi yonetmelik DEGILDIR. Emin olunmasi gereken kararlarda
resmi kaynagin ve gercek olcumun esas alinmasi gerektigini belirt.

UYDURMA YOK
Bilesen veya yonetmelik bilgisini kafadan uretme. Arac "bulunmuyor/mevcut degil"
diyorsa, sen de bilginin mevcut olmadigini soyle.

YANIT BICIMI
Kisa, net ve Turkce yanit ver. Gerektiginde madde isaretleri kullan. Gereksiz
teknik iddialardan kacin."""


def _log_tool_call(name: str, arguments: dict) -> None:
    """Arac cagrisini konsola yazar. Windows cp1254 gibi kodlamalarda emoji
    UnicodeEncodeError'a yol acabilir; o durumda ASCII yedegine duseriz."""
    try:
        print(f"  🔧 {name}({arguments})")
    except UnicodeEncodeError:
        print(f"  [arac] {name}({arguments})")


def run_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Modelin istedigi araclari calistirir ve sonuclari mesaj formatinda dondurur."""
    messages = []
    for call in tool_calls:
        function = call.get("function") or {}
        name = function.get("name")
        arguments = function.get("arguments") or {}
        if not name:  # bicimi bozuk arac cagrisi: sohbeti cökertme
            messages.append({"role": "tool", "tool_name": "unknown",
                             "content": "Bicimi bozuk arac cagrisi (isim eksik)."})
            continue
        _log_tool_call(name, arguments)

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


def run_conversation(
    messages: list[dict],
    chat=ollama_client.chat,
    model: str = ollama_client.CHAT_MODEL,
    tool_schemas: list[dict] | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> dict:
    """Sinirli (bounded) arac dongusu: model konusur, gerekirse araclari calistirir,
    en fazla `max_rounds` tur doner ve son model mesajini verir.

    `chat` disaridan verilebildigi icin bu fonksiyon Qwen olmadan (sahte chat ile)
    test edilebilir. `messages` yerinde guncellenir.
    """
    if tool_schemas is None:
        tool_schemas = tools.TOOL_SCHEMAS
    message: dict = {}
    for _ in range(max_rounds):
        message = chat(messages, model=model, tools=tool_schemas)
        messages.append(message)
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            break
        messages.extend(run_tool_calls(tool_calls))
    return message


def main() -> None:
    parser = argparse.ArgumentParser(description="Ollama tabanli otomotiv yaris asistani.")
    parser.add_argument(
        "--chat-model", default=ollama_client.CHAT_MODEL, help="Ollama sohbet modeli"
    )
    args = parser.parse_args()

    print("Otomotiv Yaris Asistani")
    print(f"  sohbet modeli: {args.chat_model}")
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
            message = run_conversation(messages, model=args.chat_model)
        except RuntimeError as exc:
            print(f"\nHata: {exc}\n")
            continue

        print(f"\nAsistan > {(message.get('content') or '').strip()}\n")


if __name__ == "__main__":
    main()
