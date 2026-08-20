"""JSON kaynaklarından SQLite veritabanını kurar.

Çalıştırma:  python kurulum.py
Kaynaklar:
  data/tanimli_terimler_1000.json  - 1000 tanımlı biyoloji terimi (kaynak sayfa + URL ile)
  data/biyoloji_benchmark.jsonl    - 102 gerçek sınav sorusu (5 şıklı, cevap anahtarlı)
"""

import json
from pathlib import Path

from koc.db import VERITABANI, baglan, normalize, semayi_kur

VERI = Path(__file__).resolve().parent / "data"


def terimleri_aktar(baglanti) -> int:
    kayitlar = json.loads((VERI / "tanimli_terimler_1000.json").read_text(encoding="utf-8"))
    baglanti.execute("DELETE FROM terimler")
    baglanti.executemany(
        """INSERT INTO terimler (terim, terim_norm, tanim, brans, kitap_sayfasi)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (
                k["terim"],
                normalize(k["terim"]),
                k["tanim"],
                k.get("brans"),
                k.get("kitap_sayfasi"),
            )
            for k in kayitlar
            if k.get("terim") and k.get("tanim")
        ],
    )
    baglanti.commit()
    return baglanti.execute("SELECT COUNT(*) FROM terimler").fetchone()[0]


def sorulari_aktar(baglanti) -> int:
    satirlar = (VERI / "biyoloji_benchmark.jsonl").read_text(encoding="utf-8").splitlines()
    kayitlar = [json.loads(s) for s in satirlar if s.strip()]
    baglanti.execute("DELETE FROM sorular")
    baglanti.executemany(
        "INSERT INTO sorular (soru, secenekler, dogru_cevap, bolum) VALUES (?, ?, ?, ?)",
        [
            (
                k["soru"],
                json.dumps(k["secenekler"], ensure_ascii=False),
                int(k["cevap"]),
                k.get("bolum"),
            )
            for k in kayitlar
        ],
    )
    baglanti.commit()
    return baglanti.execute("SELECT COUNT(*) FROM sorular").fetchone()[0]


if __name__ == "__main__":
    VERITABANI.parent.mkdir(parents=True, exist_ok=True)
    baglanti = baglan()
    semayi_kur(baglanti)

    print(f"terimler   : {terimleri_aktar(baglanti)} kayıt")
    print(f"sorular    : {sorulari_aktar(baglanti)} kayıt")
    print(f"veritabanı : {VERITABANI}")

    # Hızlı doğrulama
    from koc.db import soru_getir, terim_bul

    print("\n-- 'mayoz' araması --")
    kayitlar, kademe = terim_bul(baglanti, "mayoz")
    for k in kayitlar:
        print(f"  [{kademe}] {k['terim']} (s.{k['kitap_sayfasi']}) -> {k['tanim'][:60]}...")

    print("\n-- olmayan terim --")
    print(f"  {terim_bul(baglanti, 'kuantum fotosentezi')}")

    print("\n-- konu araması: 'mayoz' --")
    for s in soru_getir(baglanti, konu="mayoz", adet=1):
        print(f"  #{s['soru_id']} {s['soru'][:80]}...")
        print(f"  şıklar: {len(s['secenekler'])} adet, dogru_cevap alanı yok: {'dogru_cevap' not in s}")
