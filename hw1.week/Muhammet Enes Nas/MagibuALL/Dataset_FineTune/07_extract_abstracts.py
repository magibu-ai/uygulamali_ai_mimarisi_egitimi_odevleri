"""
07_extract_abstracts.py

texts/*.json icindeki TUM sayfalardan (front-matter filtresine bakmaksizin,
cunku bazi ozel sayilarda ozet blogu ile kunye/yazim-kurallari metni ayni
sayfa akisinda ic ice gecebiliyor) sadece gercek Turkce ozetleri (ÖZ ...
Anahtar Kelimeler:) regex ile ayiklar.

Bu bloklar kendi icinde butunlukli, yogun, gercek bilimsel bulgu iceren
metinlerdir (Amac/Gerec ve Yontem/Sonuc ve Tartisma) - QA uretimi icin
serpistirilmis tam metin sayfalarindan cok daha guvenilir bir kaynak.

Cikti: data/abstracts.json -> [{"source_file":..., "text": "ÖZ ... Anahtar
Kelimeler: ..."}, ...]
"""
import os
import re
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
TEXTS_DIR = os.path.join(HERE, "texts")
OUT_PATH = os.path.join(HERE, "data", "abstracts.json")

# ÖZ basligindan Anahtar Kelimeler: satirinin sonuna kadar (o satir dahil)
ABSTRACT_RE = re.compile(
    r"\nÖZ\n(.*?Anahtar Kelimeler:.*?)(?=\n\S|\n\n\n|\Z)",
    re.DOTALL,
)


def main():
    json_paths = sorted(glob.glob(os.path.join(TEXTS_DIR, "*.json")))
    all_abstracts = []

    for jp in json_paths:
        base = os.path.basename(jp)
        with open(jp, "r", encoding="utf-8") as f:
            record = json.load(f)
        full_text = "\n".join(record.get("pages", []))

        for m in ABSTRACT_RE.finditer(full_text):
            block = m.group(1).strip()
            # cok kisa/bozuk eslesmeleri ele (gercek ozetler genelde 400+ karakter)
            if len(block) < 300:
                continue
            all_abstracts.append({"source_file": base, "text": "ÖZ\n" + block})

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_abstracts, f, ensure_ascii=False, indent=2)

    print(f"Toplam {len(all_abstracts)} ozet bulundu -> {OUT_PATH}")
    from collections import Counter
    per_file = Counter(a["source_file"] for a in all_abstracts)
    for name, count in sorted(per_file.items()):
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
