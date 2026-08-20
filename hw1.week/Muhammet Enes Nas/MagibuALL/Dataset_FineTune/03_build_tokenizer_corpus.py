import os
import re
import glob
import json
import random
from collections import Counter

from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0  # deterministik sonuc icin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
TEXTS_DIR = os.path.join(ROOT, "texts")
OUT_PATH = os.path.join(ROOT, "corpus.txt")
DROPPED_LOG_PATH = os.path.join(ROOT, "data", "dropped_pages_by_lang.json")

MIN_LINE_LEN = 15  # bu uzunluktan kisa satirlar (muhtemelen gurultu) atlanir
MIN_PAGE_CHARS_FOR_DETECT = 40  # bundan kisa sayfalarda dil tespiti guvenilir degil
MIN_LINE_CHARS_FOR_LANG_CHECK = 30  # bu uzunluktaki satirlarda ayrica dil kontrolu yapilir
TARGET_LANG = "tr"
SHUFFLE = False
SEED = 42

# Tokenizer icin "saf bilgi" disinda kalan idari/kunye satirlari (link,
# telefon/faks, e-posta, ORCID, ISSN, gonderim/kabul/yayin tarihleri,
# editor/hakem/yayin kurulu isim-unvan satirlari vb.). Bu desenlerden
# herhangi biriyle eslesen satir tamamen atlanir.
NOISE_LINE_PATTERNS = {
    "url_doi": re.compile(r"https?://\S+|www\.\S+|\bdoi\s*[:.]?\s*10\.\d{4,9}/\S+|\b10\.\d{4,9}/\S+", re.IGNORECASE),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\be-posta\b|\be-mail\b", re.IGNORECASE),
    "phone_fax": re.compile(r"\btel(efon)?\.?\s*[:/]|\bphone\b|\bfaks\b|\bfax\b", re.IGNORECASE),
    "orcid": re.compile(r"\borcid\b", re.IGNORECASE),
    "issn": re.compile(r"\beissn\b|\bissn\b", re.IGNORECASE),
    "submission_dates": re.compile(
        r"\bgeli[şs]\s*tarihi\b|\bkabul\s*tarihi\b|\bya[yı]+[ıi]nlanma\s*tarihi\b|\breceived\b|\baccepted\b|\bpublished\b",
        re.IGNORECASE,
    ),
    "editorial_masthead": re.compile(
        r"ba[şs]\s*edit[öo]r|edit[öo]r(ler)?\s*:|alan\s*edit[öo]r|yay[ıi]n\s*kurulu|dan[ıi][şs]ma\s*kurulu|"
        r"editorial\s*board|sorumlu\s*yazar|corresponding\s*author|yaz[ıi][şs]ma\s*yazar",
        re.IGNORECASE,
    ),
    "journal_self_reference": re.compile(
        r"dergipark\.org\.tr|journal of faculty of pharmacy of ankara university|"
        r"ankara üniversitesi eczacılık fakültesi dergisi",
        re.IGNORECASE,
    ),
    # Yazar/editor kurul listelerinde satirlar tipik olarak "... Universitesi/
    # University, Sehir, TURKIYE/Turkey" seklinde biter (kurum adresi).
    # Gercek bilimsel cumleler boyle bitmez, bu yuzden guvenle atilabilir.
    "institution_address_line": re.compile(r",\s*(t[üu]rk[iı]ye|turkey)\.?\s*$", re.IGNORECASE),
}

# Bir sayfayi TAMAMEN "on kisim" (kapak / dergi yazi-yayin kurulu listesi /
# icindekiler) sayip elemek icin kullanilan sayfa-seviyesi isaretler. Bu
# sayfalarda "Prof.Dr. Ad Soyad, Ankara University, ..." gibi isim+kurum
# satirlari NOISE_LINE_PATTERNS'daki tekil satir desenleriyle yakalanamiyor
# (ozel isim iceriyorlar), bu yuzden sayfa butunuyle atlanir.
FRONT_MATTER_PAGE_PATTERNS = [
    re.compile(r"derg[iı]\s*yaz[ıi]\s*kurulu|editorial\s*management", re.IGNORECASE),
    re.compile(r"yay[ıi]n\s*kurulu|editorial\s*board\s*members?", re.IGNORECASE),
    re.compile(r"[iİ]ç[iİ]ndek[iİ]ler|table\s*of\s*contents", re.IGNORECASE),
    re.compile(r"journal of faculty of\s*\r?\n?\s*pharmacy", re.IGNORECASE),
    re.compile(r"(\(\d{1,4}\s*-\s*\d{1,4}\)\s*){2,}"),  # TOC'taki tekrarlayan sayfa araligi (1-13), (88-96) vb.
]


def is_front_matter_page(page_text: str) -> bool:
    return any(p.search(page_text) for p in FRONT_MATTER_PAGE_PATTERNS)


def noise_reason(line: str):
    for name, pattern in NOISE_LINE_PATTERNS.items():
        if pattern.search(line):
            return name
    return None


def is_turkish_line(line: str) -> bool:
    """Turkce olarak isaretlenmis bir sayfa icindeki tek bir satiri kontrol eder.

    Bazi sayfalarda Turkce ana metnin yaninda Ingilizce ozet/cumle de
    bulunabiliyor (dergi sayfa duzeni geregi). Kisa satirlarda (formul,
    referans no, vb.) dil tespiti guvenilir olmadigi icin sadece yeterince
    uzun satirlar bu ek kontrolden gecirilir; kisa satirlar sayfa zaten
    Turkce kabul edildiginden dogrudan tutulur.
    """
    if len(line) < MIN_LINE_CHARS_FOR_LANG_CHECK:
        return True
    try:
        return detect(line) == TARGET_LANG
    except LangDetectException:
        return True


def is_turkish_page(page_text: str) -> bool:
    """Sayfa metninin Turkce olup olmadigini tespit eder.

    Cok kisa sayfalarda (baslik/bos sayfa vb.) langdetect guvenilmez, bu
    durumda temkinli davranip sayfayi ELER (Ingilizce sizmasini onlemek,
    az miktarda Turkce icerik kaybetmekten daha onemli).
    """
    text = page_text.strip()
    if len(text) < MIN_PAGE_CHARS_FOR_DETECT:
        return False
    try:
        return detect(text) == TARGET_LANG
    except LangDetectException:
        return False


def main():
    json_paths = sorted(glob.glob(os.path.join(TEXTS_DIR, "*.json")))
    if not json_paths:
        print(f"{TEXTS_DIR} altinda .json bulunamadi. Once 02_pdf_to_text.py calistirin.")
        return

    all_lines = []
    dropped = []  # {"file":..., "page_index":..., "detected_lang" or "too_short"}
    noise_counts = Counter()
    kept_pages = 0
    total_pages = 0

    for path in json_paths:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        base = os.path.basename(path)

        for idx, page_text in enumerate(record.get("pages", [])):
            total_pages += 1
            text = (page_text or "").strip()

            if len(text) < MIN_PAGE_CHARS_FOR_DETECT:
                dropped.append({"file": base, "page_index": idx, "reason": "too_short"})
                continue

            if is_front_matter_page(text):
                dropped.append({"file": base, "page_index": idx, "reason": "front_matter"})
                continue

            try:
                lang = detect(text)
            except LangDetectException:
                dropped.append({"file": base, "page_index": idx, "reason": "detect_failed"})
                continue

            if lang != TARGET_LANG:
                dropped.append({"file": base, "page_index": idx, "reason": f"lang={lang}"})
                continue

            kept_pages += 1
            for line in text.splitlines():
                line = line.strip()
                if len(line) < MIN_LINE_LEN:
                    continue
                reason = noise_reason(line)
                if reason:
                    noise_counts[reason] += 1
                    continue
                if is_turkish_line(line):
                    all_lines.append(line)

    if SHUFFLE:
        random.seed(SEED)
        random.shuffle(all_lines)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))

    os.makedirs(os.path.dirname(DROPPED_LOG_PATH), exist_ok=True)
    with open(DROPPED_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(dropped, f, ensure_ascii=False, indent=2)

    total_chars = sum(len(l) for l in all_lines)
    print(f"{len(json_paths)} dosyadan {total_pages} sayfa tarandi.")
    print(f"  Turkce kabul edilen sayfa: {kept_pages}")
    print(f"  elenen sayfa: {len(dropped)} (detay: {DROPPED_LOG_PATH})")
    if noise_counts:
        print(f"  kunye/gurultu nedeniyle elenen satir: {sum(noise_counts.values())}")
        for name, count in noise_counts.most_common():
            print(f"    - {name}: {count}")
    print(f"{len(all_lines)} satir, {total_chars:,} karakter -> {OUT_PATH}")


if __name__ == "__main__":
    main()
