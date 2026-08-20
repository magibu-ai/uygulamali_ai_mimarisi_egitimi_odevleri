"""
README'deki örnek konuşmaları üretir.

Asistana sabit bir soru listesi sorar, araç çağrılarını ve cevapları yakalar,
sonucu Markdown olarak `ornek_konusmalar.md` dosyasına yazar. Böylece README'ye
elle kopyalanan (ve zamanla gerçeği yansıtmayan) çıktı olmaz.

Kullanım:
    python demo_konusmalar.py
"""

from __future__ import annotations

import io
import contextlib
import os

from agent import Agent

# Her senaryo, farklı bir araç yolunu zorlamak için seçildi.
SENARYOLAR = [
    ("Araçsız cevap", "Transformer mimarisindeki attention mekanizmasını iki cümleyle anlat."),
    ("Hesap makinesi", "Bir ürün 1250 TL, üzerine %20 KDV eklenip 3 taksite bölünürse taksit ne kadar olur?"),
    ("Hava durumu", "Yarın Trabzon'a gideceğim, yanıma mont almalı mıyım?"),
    ("Döviz + hesap (zincirleme)", "Elimde 500 dolar var, bugünün kuruyla kaç TL eder? Bunun %18'ini vergiye ayırırsam elimde ne kalır?"),
    ("İnternet araması", "Türkiye'nin en son açıklanan yıllık enflasyon oranı kaç?"),
    ("Tarih hesabı", "Bugün ayın kaçı ve 2027 yılbaşına kaç gün kaldı?"),
    ("Kod çalıştırma", "1'den 1000'e kadar olan asal sayıların toplamını hesapla."),
    ("Hafıza — kaydet", "Not al: sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum."),
    ("Hafıza — hatırla", "Bana kahve tercihimi söyler misin?"),
]


def main() -> None:
    agent = Agent(verbose=True)
    parcalar: list[str] = []

    for baslik, soru in SENARYOLAR:
        print(f"\n{'=' * 70}\n### {baslik}\n{'=' * 70}")
        print(f"👤 {soru}\n")

        # Araç çağrısı loglarını yakala ki markdown'a da girsin.
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            cevap = agent.ask(soru)
        loglar = tampon.getvalue().strip()

        print(loglar)
        print(f"\n🤖 {cevap}")

        blok = [f"### {baslik}\n", f"**👤 Kullanıcı:** {soru}\n"]
        if loglar:
            blok.append(f"```\n{loglar}\n```\n")
        else:
            blok.append("_(araç çağrısı yok — model doğrudan cevapladı)_\n")
        blok.append(f"**🤖 Asistan:** {cevap}\n")
        parcalar.append("\n".join(blok))

        # Hafıza senaryoları hariç her soru bağımsız değerlendirilsin.
        if not baslik.startswith("Hafıza"):
            agent.reset()

    metin = "\n---\n\n".join(parcalar)
    hedef = os.path.join(os.path.dirname(__file__), "ornek_konusmalar.md")
    with open(hedef, "w", encoding="utf-8") as fh:
        fh.write("# Örnek Konuşmalar\n\n")
        fh.write("_Bu dosya `demo_konusmalar.py` ile lokalde üretildi._\n\n---\n\n")
        fh.write(metin)
    print(f"\n✅ Yazıldı: {hedef}")


if __name__ == "__main__":
    main()
