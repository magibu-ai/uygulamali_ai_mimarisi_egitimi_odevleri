"""
Tüm scraper ve bulk generator çıktılarını ana tr.json ve eng.json dosyalarına birleştirir.
Ayrıca fixed format dosyalarını da günceller.

Kullanım:
  python scrapers/merge_all.py
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
FIXED_DIR = os.path.join(DATA_DIR, "fixed")
SCRAPERS_DIR = BASE_DIR

# Hand-written entry counts (first N entries in main files are hand-written)
HANDWRITTEN_EN = 45
HANDWRITTEN_TR = 49

# Scraper + bulk output dosyaları
SCRAPER_FILES_EN = [
    "so_eng.json",
    "github_eng.json",
    "wiki_eng.json",
    "devto_eng.json",
    "hf_eng.json",
    "arxiv_eng.json",
    "reddit_eng.json",
    "pwc_eng.json",
    "bulk_en.json",
    "bulk_en2.json",
    "bulk_en3.json",
    "bulk_en4.json",
    "bulk_en5.json",
    "bulk_en6.json",
    "bulk_en7.json",
    "bulk_en8.json",
    "bulk_en9.json",
    "bulk_en10.json",
    "bulk_en11.json",
    "bulk_en12.json",
    "bulk_en13.json",
    "bulk_en14.json",
    "bulk_en15.json",
    "bulk_en16.json",
    "bulk_en17.json",
    "bulk_en18.json",
    "bulk_en19.json",
    "bulk_en20.json",
    "bulk_en21.json",
    "bulk_en22.json",
    "bulk_en23.json",
    "bulk_en24.json",
    "bulk_en25.json",
    "bulk_en26.json",
    "bulk_en27.json",
    "bulk_en28.json",
    "bulk_en29.json",
    "bulk_en30.json",
    "bulk_en31.json",
    "bulk_en32.json",
    "bulk_en33.json",
    "bulk_en34.json",
]

SCRAPER_FILES_TR = [
    "so_tr.json",
    "github_tr.json",
    "wiki_tr.json",
    "devto_tr.json",
    "hf_tr.json",
    "arxiv_tr.json",
    "reddit_tr.json",
    "pwc_tr.json",
    "bulk_tr.json",
    "bulk_tr2.json",
    "bulk_tr3.json",
    "bulk_tr4.json",
    "bulk_tr5.json",
    "bulk_tr6.json",
    "bulk_tr7.json",
    "bulk_tr8.json",
    "bulk_tr9.json",
    "bulk_tr10.json",
    "bulk_tr11.json",
    "bulk_tr12.json",
    "bulk_tr13.json",
    "bulk_tr14.json",
    "bulk_tr15.json",
    "bulk_tr16.json",
    "bulk_tr17.json",
    "bulk_tr18.json",
    "bulk_tr19.json",
    "bulk_tr20.json",
    "bulk_tr21.json",
    "bulk_tr22.json",
    "bulk_tr23.json",
    "bulk_tr24.json",
    "bulk_tr25.json",
    "bulk_tr26.json",
    "bulk_tr27.json",
    "bulk_tr28.json",
    "bulk_tr29.json",
    "bulk_tr30.json",
    "bulk_tr31.json",
    "bulk_tr32.json",
    "bulk_tr33.json",
    "bulk_tr34.json",
    "bulk_tr35.json",
    "bulk_tr36.json",
]

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"train": []}

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def main():
    # Ana dosyaları yükle
    eng_path = os.path.join(DATA_DIR, "eng.json")
    tr_path = os.path.join(DATA_DIR, "tr.json")

    eng_data = load_json(eng_path)
    tr_data = load_json(tr_path)

    # Sadece hand-written entries'i tut (ilk N entry)
    eng_handwritten = eng_data["train"][:HANDWRITTEN_EN]
    tr_handwritten = tr_data["train"][:HANDWRITTEN_TR]

    print(f"Hand-written EN: {len(eng_handwritten)}")
    print(f"Hand-written TR: {len(tr_handwritten)}")

    # Sıfırdan başla
    eng_entries = list(eng_handwritten)
    tr_entries = list(tr_handwritten)

    # EN scraper + bulk dosyalarını birleştir
    print("\n--- EN Files ---")
    for fname in SCRAPER_FILES_EN:
        fpath = os.path.join(SCRAPERS_DIR, fname)
        scraped = load_json(fpath)
        count = len(scraped.get("train", []))
        eng_entries.extend(scraped.get("train", []))
        print(f"  {fname}: {count} entries")

    # TR scraper + bulk dosyalarını birleştir
    print("\n--- TR Files ---")
    for fname in SCRAPER_FILES_TR:
        fpath = os.path.join(SCRAPERS_DIR, fname)
        scraped = load_json(fpath)
        count = len(scraped.get("train", []))
        tr_entries.extend(scraped.get("train", []))
        print(f"  {fname}: {count} entries")

    # Normal format kaydet
    save_json({"train": eng_entries}, eng_path)
    save_json({"train": tr_entries}, tr_path)

    # Fixed format kaydet (list of {"messages": [user_msg, asst_msg]})
    eng_fixed = [{"messages": entry} for entry in eng_entries]
    tr_fixed = [{"messages": entry} for entry in tr_entries]

    os.makedirs(FIXED_DIR, exist_ok=True)
    save_json(eng_fixed, os.path.join(FIXED_DIR, "eng_fixed.json"))
    save_json(tr_fixed, os.path.join(FIXED_DIR, "tr_fixed.json"))

    print(f"\n=== RESULTS ===")
    print(f"eng.json: {len(eng_entries)} entries")
    print(f"tr.json: {len(tr_entries)} entries")
    print(f"eng_fixed.json: {len(eng_fixed)} entries")
    print(f"tr_fixed.json: {len(tr_fixed)} entries")
    print("Done!")

if __name__ == "__main__":
    main()
