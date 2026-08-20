"""
06_extract_clean_text_per_issue.py

texts/*.json (sayfa sayfa ham metin) icinden, 03_build_tokenizer_corpus.py'nin
zaten hesapladigi data/dropped_pages_by_lang.json'i kullanarak SADECE Turkce
ve on-kisim/kapak olmayan sayfalari alir, her issue icin TEK BIR temiz metin
dosyasi yazar (data/clean_text/<issue>.txt). Boylece QA uretimi icin buyuk
parcalar halinde okunabilir, Ingilizce/kapak/editor kurulu sayfalari tekrar
elemek gerekmez.

Ayrica her dosyanin karakter sayisini yazdirir (2500 hedefine gore dosya
basina kac QA uretilecegini orantili hesaplamak icin).
"""
import os
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
TEXTS_DIR = os.path.join(HERE, "texts")
DROPPED_LOG_PATH = os.path.join(HERE, "data", "dropped_pages_by_lang.json")
OUT_DIR = os.path.join(HERE, "data", "clean_text")


def main():
    with open(DROPPED_LOG_PATH, "r", encoding="utf-8") as f:
        dropped = json.load(f)
    excluded = {(d["file"], d["page_index"]) for d in dropped}

    os.makedirs(OUT_DIR, exist_ok=True)

    json_paths = sorted(glob.glob(os.path.join(TEXTS_DIR, "*.json")))
    summary = []
    for jp in json_paths:
        base = os.path.basename(jp)
        with open(jp, "r", encoding="utf-8") as f:
            record = json.load(f)
        pages = record.get("pages", [])
        kept = [p for idx, p in enumerate(pages) if (base, idx) not in excluded]
        clean_text = "\n\n".join(kept)

        out_name = base.replace(".json", ".txt")
        out_path = os.path.join(OUT_DIR, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(clean_text)

        summary.append((out_name, len(pages), len(kept), len(clean_text)))

    total_chars = sum(s[3] for s in summary)
    print(f"{'dosya':45} {'toplam_sayfa':>12} {'temiz_sayfa':>12} {'karakter':>10}")
    for name, total_pages, kept_pages, chars in summary:
        print(f"{name:45} {total_pages:>12} {kept_pages:>12} {chars:>10}")
    print(f"\nTOPLAM temiz karakter: {total_chars:,}")

    with open(os.path.join(HERE, "data", "clean_text_summary.json"), "w", encoding="utf-8") as f:
        json.dump(
            [{"file": n, "total_pages": tp, "kept_pages": kp, "chars": c} for n, tp, kp, c in summary],
            f, ensure_ascii=False, indent=2,
        )


if __name__ == "__main__":
    main()
