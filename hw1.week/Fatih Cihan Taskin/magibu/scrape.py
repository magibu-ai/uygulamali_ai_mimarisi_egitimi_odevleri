"""
Giresun kültürel özellikleri için web scraping.

Bu betik, kamuya açık kaynaklardan Giresun kültürü metinlerini toplar ve
scraped_raw.jsonl dosyasına yazar. Toplanan ham metin, Q&A üretimi için
kaynak olarak kullanılır (bkz. facts.py / qa_pairs.py).

NOT: Bu betik yerel makinede çalıştırılmak içindir. Çalıştırma ortamının
ağı bazı siteleri (ör. Wikipedia) engelliyorsa buradan çalışmayabilir;
kendi bilgisayarınızda çalıştırın.

Kullanım:
    uv run python scrape.py
"""

import json
import time
import re

import requests
from bs4 import BeautifulSoup

# Kaynak sayfalar. Giresun kültürüne dair kamuya açık, olgu içerikli sayfalar.
SOURCES = [
    "https://www.giresun.gov.tr/giresun-kulturu",
    "https://www.giresun.gov.tr/kultur-ve-sanat",
    "https://karadeniz.gov.tr/yemek-kulturu-5/",
    "https://karadeniz.gov.tr/halk-muzigi-7/",
    "https://tr.wikipedia.org/wiki/Giresun_Adas%C4%B1",
    "https://tr.wikipedia.org/wiki/Giresun",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def clean_text(text: str) -> str:
    text = re.sub(r"\[\d+\]", "", text)        # [1] gibi dipnot işaretleri
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_paragraphs(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    paras = []
    for p in soup.find_all(["p", "li"]):
        txt = clean_text(p.get_text(" ", strip=True))
        # Çok kısa veya menü benzeri satırları ele
        if len(txt) >= 40:
            paras.append(txt)
    return paras


def scrape():
    results = []
    for url in SOURCES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            paras = extract_paragraphs(r.text)
            results.append({"url": url, "paragraphs": paras})
            print(f"[ok] {url} -> {len(paras)} paragraf")
        except Exception as e:
            print(f"[hata] {url} -> {e}")
        time.sleep(1.5)  # kaynak sunuculara nazik davran

    with open("scraped_raw.jsonl", "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    total = sum(len(r["paragraphs"]) for r in results)
    print(f"\nToplam {total} paragraf 'scraped_raw.jsonl' dosyasına yazıldı.")


if __name__ == "__main__":
    scrape()
