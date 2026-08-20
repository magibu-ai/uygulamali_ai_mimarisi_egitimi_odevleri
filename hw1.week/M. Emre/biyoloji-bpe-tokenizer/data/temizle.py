"""Biyoloji terimleri veri setini temizler.

Yaptigi isler:
  1. Bastaki/sondaki bosluklari kirpar, bos satirlari atar.
  2. Konu-disi kelimeleri (trafik/genel/fizik) cikarir.
  3. Tekrarlari ayiklar (sirayi korur).
  4. Her terimi kucuk harfe cevirir (zaten kucuk ama garanti).

Cikti: temiz_biyoloji.txt  (satir basina bir terim)
"""

import os

SRC = os.path.join(os.path.dirname(__file__), "biyoloji_terimler.txt")
OUT = os.path.join(os.path.dirname(__file__), "temiz_biyoloji.txt")

# Konu disi oldugu icin cikarilacak kelimeler.
CIKAR = {
    # 1) Trafik / yol / arac
    "banket", "bisiklet", "bordür", "dingil", "gabari", "güzergâh",
    "kask", "kavşak", "kaykay", "kilittaşı", "levha", "motosiklet",
    "otoyol", "sürücü", "teleferik", "trafik", "turnike", "yaya",
    "bariyer", "geçit",
    # 2) Soyut / genel / sosyal
    "adap", "ahlak", "akran", "alışkanlık", "azami", "bildirme",
    "bilgi", "bilim", "duygusal", "empati", "engellilik", "gerçek",
    "gürültü", "iletişim", "intihal", "istismar", "itlaf", "kategori",
    "kaygı", "kontrol", "mesafe", "mesaj", "mobil", "olasılık",
    "optimum", "organizasyon", "parametre", "prototip", "rehabilitasyon",
    "sistem", "şiddet", "tahmin", "teori", "zorbalık",
    # 3) Fizik alet / birim
    "desibel", "hertz", "galvanometre", "odyometre", "nonius",
}


def main():
    with open(SRC, encoding="utf-8") as f:
        satirlar = [s.strip().lower() for s in f]

    temiz = []
    gorulen = set()
    atilan_konu_disi = []
    for kelime in satirlar:
        if not kelime:                      # bos satir
            continue
        if kelime in CIKAR:                 # konu disi
            atilan_konu_disi.append(kelime)
            continue
        if kelime in gorulen:               # tekrar
            continue
        gorulen.add(kelime)
        temiz.append(kelime)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(temiz) + "\n")

    print(f"Ham satir sayisi        : {len(satirlar)}")
    print(f"Cikarilan konu-disi     : {len(atilan_konu_disi)}")
    print(f"Temiz terim sayisi      : {len(temiz)}")
    print(f"Cikti dosyasi           : {OUT}")


if __name__ == "__main__":
    main()
