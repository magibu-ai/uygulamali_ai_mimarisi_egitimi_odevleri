"""Ders kitaplarini parcalayip vektor veritabanina yazar.

Calistirma:  python index_dersler.py

veri/ klasorundeki her .txt bir ders olarak islenir; dosya adi ders adi olur.
Uretilen vektorler chroma_db/ altina yazilir, tekrar calistirmak indeksi sifirlar.
"""

from __future__ import annotations

import os
import time

import ders_rag

ADIM = 2000  # Chroma'ya tek seferde yazilacak parca sayisi

# Kitap basina alinacak metin miktari. Kitaplarin tamami 11,7 milyon karakter
# tutuyor ve yaklasik 17 bin parca uretiyor; bu, gosterim amacli bir calisma icin
# gereksiz derecede buyuk. Ornekleme kitabin BASINDAN degil, esit araliklarla
# BES AYRI BOLUMUNDEN yapilir: boylece tek bir uniteye sikismak yerine kitabin
# genelindeki konu cesitliligi korunur.
KITAP_BASINA_KARAKTER = 500_000
BOLUM_SAYISI = 5


def ornekle(metin: str, hedef: int = KITAP_BASINA_KARAKTER) -> str:
    if len(metin) <= hedef:
        return metin
    pay = hedef // BOLUM_SAYISI
    adim = len(metin) // BOLUM_SAYISI
    parcalar = []
    for i in range(BOLUM_SAYISI):
        bas = i * adim
        kesit = metin[bas : bas + pay]
        # Kesit ortada baslamasin diye ilk satiri atip son satiri tamamlamaya birak.
        if "\n" in kesit:
            kesit = kesit.split("\n", 1)[1]
        parcalar.append(kesit)
    return "\n".join(parcalar)


def kitaplari_oku() -> dict[str, str]:
    kitaplar = {}
    for ad in sorted(os.listdir(ders_rag.VERI_YOLU)):
        if not ad.endswith(".txt"):
            continue
        ders = os.path.splitext(ad)[0]
        with open(os.path.join(ders_rag.VERI_YOLU, ad), encoding="utf-8") as f:
            ham = f.read()
        kitaplar[ders] = ornekle(ham)
    return kitaplar


if __name__ == "__main__":
    kitaplar = kitaplari_oku()
    if not kitaplar:
        raise SystemExit(f"{ders_rag.VERI_YOLU} icinde .txt bulunamadi.")

    metinler: list[str] = []
    metalar: list[dict] = []
    idler: list[str] = []

    for ders, icerik in kitaplar.items():
        parcalar = ders_rag.parcala(icerik)
        print(f"{ders:8} {len(icerik):>9} karakter -> {len(parcalar):>6} parca")
        for i, p in enumerate(parcalar):
            metinler.append(p)
            metalar.append({"ders": ders, "parca_no": i})
            idler.append(f"{ders}-{i}")

    print(f"\ntoplam {len(metinler)} parca")
    print(f"embedding uretiliyor ({ders_rag.EMBED_MODELI}, cihaz={ders_rag.cihaz()})")
    basla = time.time()
    vektorler = ders_rag.vektorlestir(metinler, ilerleme=True)
    print(f"sure: {time.time() - basla:.1f} sn | vektor boyutu: {vektorler.shape}")

    print("\nChromaDB'ye yaziliyor")
    kol = ders_rag.koleksiyon(sifirla=True)
    for i in range(0, len(idler), ADIM):
        kol.add(
            ids=idler[i : i + ADIM],
            documents=metinler[i : i + ADIM],
            embeddings=[v.tolist() for v in vektorler[i : i + ADIM]],
            metadatas=metalar[i : i + ADIM],
        )
        print(f"  {min(i + ADIM, len(idler))}/{len(idler)}")

    print(f"\nkoleksiyondaki kayit: {kol.count()}")
    print(f"veritabani: {ders_rag.DB_YOLU}")
