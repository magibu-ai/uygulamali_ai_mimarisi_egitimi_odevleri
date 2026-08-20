import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
OUT_DIR = os.path.join(ROOT, "raw_pdfs")
META_DIR = os.path.join(ROOT, "data")

JOURNAL_SLUG = "jfpanu"  # Journal of Faculty of Pharmacy of Ankara University
BASE = "https://dergipark.org.tr/en"
ARCHIVE_URL = f"{BASE}/pub/{JOURNAL_SLUG}/archive"

TARGET_YEARS = {2023, 2024, 2025, 2026}
REQUEST_DELAY_SECONDS = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; academic-data-collection/1.0)"
}

LICENSE_NOTE = "CC BY 4.0 (Journal of Faculty of Pharmacy of Ankara University)"

# 19 Temmuz 2026'da arsiv sayfasi elle dogrulanarak toplanan sayi ID'leri.
# Dinamik tarama basarisiz olursa ya da eksik kalirsa buraya duser (fallback).
FALLBACK_ISSUE_IDS = {
    2023: [73490, 75584, 77928],
    2024: [80375, 83110, 83274, 85047],
    2025: [88441, 91737, 94163, 99163],
    2026: [102964, 105161],
}


def get(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


def discover_issue_ids():
    discovered = {}
    try:
        resp = get(ARCHIVE_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        current_year = None
        year_re = re.compile(r"^(20[0-2]\d)$")
        issue_href_re = re.compile(rf"/pub/{JOURNAL_SLUG}/issue/(\d+)")

        for node in soup.descendants:
            # Metin dugumu mu, tek basina bir yil mi?
            if isinstance(node, str):
                text = node.strip()
                m = year_re.match(text)
                if m:
                    current_year = int(m.group(1))
                continue

            # <a href=".../issue/12345"> dugumu mu?
            href = node.get("href") if hasattr(node, "get") else None
            if href:
                m = issue_href_re.search(href)
                if m and current_year:
                    issue_id = int(m.group(1))
                    discovered.setdefault(current_year, set()).add(issue_id)

    except requests.RequestException as e:
        print(f"UYARI: arsiv sayfasi taranamadi ({e}). Sadece dogrulanmis fallback liste kullanilacak.")

    return {y: sorted(ids) for y, ids in discovered.items()}


def merged_issue_ids():
    discovered = discover_issue_ids()
    merged = {y: set(FALLBACK_ISSUE_IDS.get(y, [])) for y in TARGET_YEARS}
    for y, ids in discovered.items():
        if y in TARGET_YEARS:
            merged[y].update(ids)
    return {y: sorted(ids) for y, ids in merged.items()}


def try_download_issue_full_file(issue_id, out_path):
    url = f"{BASE}/download/issue-full-file/{issue_id}"
    try:
        resp = get(url)
        content_type = resp.headers.get("Content-Type", "")
        if "pdf" in content_type.lower() or resp.content[:4] == b"%PDF":
            with open(out_path, "wb") as f:
                f.write(resp.content)
            return True
    except requests.RequestException:
        pass
    return False


def download_articles_individually(issue_id, year_dir, issue_meta):
    """issue-full-file yoksa, sayi sayfasindaki her makaleyi ayri ayri indirir."""
    issue_page_url = f"{BASE}/pub/{JOURNAL_SLUG}/issue/{issue_id}"
    try:
        resp = get(issue_page_url)
    except requests.RequestException as e:
        print(f"  HATA: sayi sayfasi alinamadi ({e})")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    article_links = soup.find_all("a", href=re.compile(r"/download/article-file/(\d+)"))

    if not article_links:
        print("  UYARI: bu sayida indirilebilir makale PDF'i bulunamadi.")
        return

    for a in article_links:
        m = re.search(r"/article-file/(\d+)", a["href"])
        file_id = m.group(1)
        out_path = os.path.join(year_dir, f"jfpanu_{issue_id}_article_{file_id}.pdf")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            continue
        try:
            r = get(f"{BASE}/download/article-file/{file_id}")
            with open(out_path, "wb") as f:
                f.write(r.content)
            print(f"    makale indirildi -> {out_path}")
        except requests.RequestException as e:
            print(f"    HATA (article-file/{file_id}): {e}")
        time.sleep(REQUEST_DELAY_SECONDS)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(META_DIR, exist_ok=True)

    issue_map = merged_issue_ids()
    all_meta = []

    for year in sorted(TARGET_YEARS):
        issue_ids = issue_map.get(year, [])
        if not issue_ids:
            print(f"{year}: hic sayi bulunamadi (dinamik tarama + fallback ikisi de bos).")
            continue

        year_dir = os.path.join(OUT_DIR, str(year))
        os.makedirs(year_dir, exist_ok=True)

        for issue_id in issue_ids:
            out_path = os.path.join(year_dir, f"jfpanu_issue_{issue_id}_full.pdf")
            print(f"[{year}] sayi {issue_id} isleniyor...")

            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                print(f"  zaten var, atlandi: {out_path}")
            else:
                ok = try_download_issue_full_file(issue_id, out_path)
                time.sleep(REQUEST_DELAY_SECONDS)
                if ok:
                    print(f"  tum sayi tek PDF olarak indirildi -> {out_path}")
                else:
                    print("  issue-full-file bulunamadi, makaleler tek tek indiriliyor...")
                    download_articles_individually(issue_id, year_dir, {"year": year, "issue_id": issue_id})

            all_meta.append({
                "journal": "Journal of Faculty of Pharmacy of Ankara University (jfpanu)",
                "year": year,
                "issue_id": issue_id,
                "issue_url": f"{BASE}/pub/{JOURNAL_SLUG}/issue/{issue_id}",
                "license": LICENSE_NOTE,
            })

    meta_path = os.path.join(META_DIR, "dergipark_issues_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)
    print(f"\nMetadata kaydedildi -> {meta_path}")
    print("Bitti. Simdi 02_pdf_to_text.py ile devam edebilirsiniz.")


if __name__ == "__main__":
    main()
