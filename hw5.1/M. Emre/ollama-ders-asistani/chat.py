"""Arac cagirabilen ders calisma asistani (komut satiri).

Dongu basit:
    ogrenci sorar -> model ya cevap verir ya da bir arac cagirir
                  -> araci biz calistirir, sonucu modele geri veririz
                  -> model nihai cevabi yazar

Kullanim:
    python chat.py
    python chat.py --model qwen3:8b     # baska bir yerel model dene
"""

from __future__ import annotations

import argparse

import ollama_client
import tools

MAKS_ARAC_TURU = 5  # sonsuz arac dongusune karsi emniyet freni

# --- Sistem istemi -----------------------------------------------------------
# Bu istem uc seyi yapmak icin optimize edildi:
#   1. KAYNAK ONCELIGI  -> once ders kitabi, sonra internet. Sira sabittir.
#   2. AKTARMA DISIPLINI-> ders_ara ciktisi degistirilmeden aktarilir.
#   3. SEFFAFLIK        -> bilgi internetten geldiyse ogrenciye soylenir.
# Ucuncu madde onemli: ogrenci sinavda ders kitabindan sorumlu oldugu icin
# bilginin kaynagini bilmek zorunda.
SISTEM_ISTEMI = """Sen Turkce konusan bir ders calisma asistanisin. Elindeki ders
kitaplari: fizik, kimya, tarih.

Araclarin:
- ders_ara      : fizik, kimya veya tarih ile ilgili HER soru
- calisma_plani : "plan yap", "kac gunde biterim" gibi program istekleri
- hesapla       : sayisal islemler
- internet_ara  : ders kitaplarinda olmayan guncel veya genel bilgi

KURALLAR:
1. Ders konusu bir soru geldiginde ONCE ders_ara aracini cagir. Kendi bilginle
   cevap verme.
2. ders_ara aracinin dondurdugu metni AYNEN aktar. Uzerine bilgi ekleme,
   genisletme, duzeltme veya yorumlama yapma. Kaynak satirlarini da aynen goster.
3. ders_ara "Bilmiyorum" dondurduyse, konuyu internet_ara ile arayabilirsin.
   Ancak bu durumda cevaba mutlaka su notu ekle:
   "Bu bilgi ders kitaplarinda yok, internetten alindi."
4. Ders disi ve guncel sorular icin dogrudan internet_ara kullan.
5. Hicbir arac sonuc vermezse bilmedigini soyle. Tahmin yurutme.
6. Selamlasma ve sohbet gibi basit mesajlar icin arac cagirma.
"""


def araclari_calistir(arac_cagrilari: list[dict]) -> list[dict]:
    """Modelin istedigi araclari calistirir, sonuclari mesaj formatinda dondurur."""
    mesajlar = []
    for cagri in arac_cagrilari:
        ad = cagri["function"]["name"]
        argumanlar = cagri["function"].get("arguments") or {}
        print(f"  [arac] {ad}({argumanlar})")

        fonksiyon = tools.TOOLS.get(ad)
        if fonksiyon is None:
            cikti = f"'{ad}' adinda bir arac yok."
        else:
            try:
                cikti = fonksiyon(**argumanlar)
            except Exception as hata:  # arac hatasi sohbeti bitirmesin
                cikti = f"Arac calistirilamadi: {hata}"

        mesajlar.append({"role": "tool", "tool_name": ad, "content": cikti})
    return mesajlar


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Ollama tabanli ders calisma asistani.")
    ayristirici.add_argument("--model", default=ollama_client.CHAT_MODEL, help="Ollama sohbet modeli")
    args = ayristirici.parse_args()

    print("Ders Calisma Asistani")
    print(f"  sohbet modeli   : {args.model}")
    print(f"  embedding modeli: {__import__('ders_rag').EMBED_MODELI}")
    print("  dersler         : fizik, kimya, tarih")
    print("  cikmak icin: cik\n")

    mesajlar = [{"role": "system", "content": SISTEM_ISTEMI}]

    while True:
        try:
            soru = input("Siz > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not soru:
            continue
        if soru.lower() in {"cik", "çık", "exit", "quit"}:
            break

        mesajlar.append({"role": "user", "content": soru})

        try:
            for _ in range(MAKS_ARAC_TURU):
                mesaj = ollama_client.chat(mesajlar, model=args.model, tools=tools.TOOL_SCHEMAS)
                mesajlar.append(mesaj)
                arac_cagrilari = mesaj.get("tool_calls")
                if not arac_cagrilari:
                    break
                mesajlar.extend(araclari_calistir(arac_cagrilari))
        except RuntimeError as hata:
            print(f"\nHata: {hata}\n")
            continue

        print(f"\nAsistan > {(mesaj.get('content') or '').strip()}\n")


if __name__ == "__main__":
    main()
