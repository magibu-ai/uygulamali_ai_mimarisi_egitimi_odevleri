"""Download Turkish place names and turn them into raw training data.

Run from the data/ directory:

    python hazirla.py            # -> isimler.txt
    python temizle_isimler.py    # -> temiz_isimler.txt  (next step)

Source: github.com/nejdetkadir/il-ilce-semt-mahalleler (81 provinces, 973
districts, 51k neighbourhoods, compiled from official records).

What this does:
  * collects district + quarter + neighbourhood names
  * strips the "Mah." / "Köyü" style suffixes -- we want the *name*, not the
    label, otherwise the model just learns to append "mah" to everything
  * drops entries with digits or punctuation ("Yeni Mah. (2)" and friends)
  * removes duplicates -- "Yeşilköy" exists in 40 provinces, and a model that
    sees it 40 times will fixate on it
  * sorts, so re-running gives a byte-identical file

Output still has capitals and multi-word names ("Aşağı Hacıbey"); that is what
temizle_isimler.py is for.
"""

import collections
import json
import os
import re
import urllib.request

URL = ("https://raw.githubusercontent.com/nejdetkadir/il-ilce-semt-mahalleler/"
       "master/data/data.json")

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_FILE = os.path.join(HERE, "data.json")
OUT_FILE = os.path.join(HERE, "isimler.txt")   # temizle_isimler.py reads this

# Trailing labels: "Mah.", "Mh.", "Mahallesi", "Köyü", ...
SUFFIX = re.compile(r"\s+(Mah\.?|Mh\.?|Mahallesi|Mahalle|Köyü|Koyu)\s*$", re.IGNORECASE)
# Turkish letters and spaces only -- everything else is noise
VALID = re.compile(r"^[A-Za-zÇĞİÖŞÜçğıöşü ]+$")


def indir():
    if not os.path.exists(RAW_FILE):
        print(f"Veri indiriliyor: {URL}")
        urllib.request.urlretrieve(URL, RAW_FILE)
    return json.load(open(RAW_FILE, encoding="utf-8"))


def topla(veri):
    isimler = []
    for il in veri:
        for ilce in il["towns"]:
            isimler.append(ilce["name"])
            for semt in ilce["districts"]:
                isimler.append(semt["name"])
                for mahalle in semt["quarters"]:
                    isimler.append(mahalle["name"])
    return isimler


def temizle(isimler):
    tutulan = set()
    for ham in isimler:
        s = SUFFIX.sub("", ham.strip())
        s = re.sub(r"\s+", " ", s).strip()
        if not VALID.match(s):
            continue
        if not 2 <= len(s) <= 25:
            continue
        tutulan.add(s)
    return sorted(tutulan)


def main():
    veri = indir()
    print(f"İl sayısı: {len(veri)}")

    ham = topla(veri)
    print(f"Ham isim sayısı: {len(ham):,}")

    isimler = temizle(ham)
    print(f"Temiz benzersiz isim: {len(isimler):,}")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(isimler) + "\n")
    print(f"-> {OUT_FILE}")

    uzunluk = [len(x) for x in isimler]
    print(f"\nUzunluk  min:{min(uzunluk)}  ort:{sum(uzunluk) / len(uzunluk):.1f}  "
          f"max:{max(uzunluk)}")
    sayac = collections.Counter("".join(isimler))
    print(f"Farklı karakter: {len(sayac)}")
    print(f"Karakter seti: {''.join(sorted(sayac))}")
    print("\nÖrnekler:")
    for x in isimler[::2000][:10]:
        print("  ", x)
    print("\nSıradaki adım:  python temizle_isimler.py")


if __name__ == "__main__":
    main()
