"""Triyaj Asistanı — araç çağırabilen terminal sohbeti.

Döngü çok basit:
    kullanıcı sorar -> model ya cevap verir ya da bir araç çağırır
                    -> aracı biz çalıştırır, sonucu modele geri veririz
                    -> model nihai cevabı yazar

Kullanım:
    python3 chat.py
    python3 chat.py --chat-model llama3.1:8b     # başka bir modelle dene
"""

import argparse

import ollama_client
import tools

MAX_TOOL_ROUNDS = 5  # sonsuz araç döngüsüne karşı emniyet freni

# --- Sistem istemi (system prompt) ---------------------------------------
# Modelin ROLÜNÜ, SINIRLARINI ve hangi aracı ne zaman çağıracağını burada net
# tanımlıyoruz. İyi bir triyaj asistanının en kritik iki kuralı:
#   (1) tanı KOYMAMAK,  (2) acil durumu ASLA küçümsememek.
# Not: Bu istem bilinçli olarak KISA tutulmuştur. Yerel 7B/14B modellerde uzun
# ve çok kurallı sistem istemleri araç çağırma (tool calling) başarısını belirgin
# şekilde düşürüyor; kısa ve net istem ise ~%95 isabetle doğru aracı seçtiriyor.
SYSTEM_PROMPT = """Sen Türkçe konuşan bir sağlık triyaj (yönlendirme) asistanısın.
YALNIZCA Türkçe yanıt ver; başka bir dil (İngilizce, Çince vb.) kullanma.
Tanı koymaz, ilaç/doz önermezsin; kullanıcıyı doğru basamağa (acil / poliklinik /
evde takip) yönlendirirsin.

Araç kullanımı:
- Kullanıcı bir belirti/şikâyet anlatırsa aciliyet_degerlendir aracını çağır.
- Bir hastalık/durum hakkında bilgi sorulursa tibbi_bilgi_ara aracını çağır.
- Bir şehirde hastane/eczane sorulursa yakin_saglik_kurulusu aracını çağır.
- Güncel/genel bilgi için internet_arama aracını çağır.
- Sayısal bir hesap (VKİ, yüzde, doz vb.) gerekiyorsa hesap_makinesi aracını çağır.

Araçların sonucunu kullanıcıya sade biçimde aktar; kendi tıbbi bilgini EKLEME.
aciliyet_degerlendir sonucundaki aciliyet düzeyini olduğu gibi ilet.
tibbi_bilgi_ara "bilgim yok" derse sen de bilmediğini söyle, belirti uydurma.
Sadece selamlaşma ve basit sohbette araç çağırma. Ciddi durumlarda kısaca
hatırlat: kesin tanı için bir sağlık kuruluşuna başvurulmalıdır."""


def araclari_calistir(tool_calls: list[dict]) -> list[dict]:
    """Modelin istediği araçları çalıştırır ve sonuçları mesaj formatında döndürür."""
    mesajlar = []
    for call in tool_calls:
        isim = call["function"]["name"]
        argumanlar = call["function"].get("arguments") or {}
        print(f"  🔧 {isim}({argumanlar})")

        fonksiyon = tools.TOOLS.get(isim)
        if fonksiyon is None:
            cikti = f"'{isim}' adında bir araç yok."
        else:
            try:
                cikti = fonksiyon(**argumanlar)
            except Exception as exc:  # araç hatası sohbeti bitirmesin
                cikti = f"Araç çalıştırılamadı: {exc}"

        mesajlar.append({"role": "tool", "tool_name": isim, "content": cikti})
    return mesajlar


def main() -> None:
    parser = argparse.ArgumentParser(description="Araç çağırmalı triyaj asistanı.")
    parser.add_argument("--chat-model", default=ollama_client.CHAT_MODEL, help="Ollama sohbet modeli")
    args = parser.parse_args()

    print("🏥 Triyaj Asistanı")
    print(f"   sohbet modeli   : {args.chat_model}")
    print(f"   embedding modeli: {ollama_client.EMBED_MODEL['name']}")
    print("   Not: Bu asistan tanı koymaz, yalnızca yönlendirir. Acil durumda 112.")
    print("   çıkmak için: çık\n")

    mesajlar = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            soru = input("Siz > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not soru:
            continue
        if soru.lower() in {"çık", "cik", "exit", "quit", "q"}:
            break

        mesajlar.append({"role": "user", "content": soru})

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                mesaj = ollama_client.chat(
                    mesajlar, model=args.chat_model, tools=tools.TOOL_SCHEMAS
                )
                mesajlar.append(mesaj)
                tool_calls = mesaj.get("tool_calls")
                if not tool_calls:
                    break
                mesajlar.extend(araclari_calistir(tool_calls))
        except RuntimeError as exc:
            print(f"\nHata: {exc}\n")
            continue

        print(f"\nAsistan > {(mesaj.get('content') or '').strip()}\n")


if __name__ == "__main__":
    main()
