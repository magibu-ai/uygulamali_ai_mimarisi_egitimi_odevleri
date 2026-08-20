"""
02_pdf_to_text.py

raw_pdfs/ altindaki tum PDF'leri metne cevirir.
Her PDF icin:
  - texts/<isim>.txt      : temizlenmis duz metin (tokenizer korpusu icin)
  - texts/<isim>.json     : sayfa sayfa metin + metadata (dataset uretimi icin)

Once pdfplumber dener, o basarisiz olursa (bazi taranmis/gorsel agirlikli
PDF'lerde pdfplumber zayif kalabiliyor) PyMuPDF (fitz) ile dener.
"""
import os
import re
import json
import glob

import pdfplumber

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
RAW_DIR = os.path.join(ROOT, "raw_pdfs")
OUT_DIR = os.path.join(ROOT, "texts")

# Dergi sayfalarinda tekrar eden, bilgi degeri olmayan satirlari ayiklamak
# icin basit desenler. Kendi dergi(ler)inizin gercek header/footer'ina gore
# bu listeyi genisletin.
NOISE_PATTERNS = [
    r"^\s*sayfa\s*\d+\s*$",
    r"^\s*\d+\s*$",  # tek basina sayfa numarasi
    r"^\s*eczac[ıi]\s*derg[iı]si\s*$",
    r"^\s*www\.[a-z0-9.-]+\s*$",
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)


def clean_page_text(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    for ln in lines:
        if NOISE_RE.match(ln.strip()):
            continue
        cleaned.append(ln.rstrip())
    # coklu bos satirlari teke indir
    out = "\n".join(cleaned)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def extract_with_pdfplumber(path: str):
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            raw = page.extract_text() or ""
            pages.append(clean_page_text(raw))
    return pages


def extract_with_fitz(path: str):
    pages = []
    doc = fitz.open(path)
    for page in doc:
        raw = page.get_text("text") or ""
        pages.append(clean_page_text(raw))
    doc.close()
    return pages


def extract_pdf(path: str):
    try:
        pages = extract_with_pdfplumber(path)
        if any(p.strip() for p in pages):
            return pages, "pdfplumber"
    except Exception as e:
        print(f"  pdfplumber hatasi: {e}")

    if HAS_FITZ:
        try:
            pages = extract_with_fitz(path)
            return pages, "pymupdf"
        except Exception as e:
            print(f"  pymupdf hatasi: {e}")

    return [], "basarisiz"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    pdf_paths = sorted(glob.glob(os.path.join(RAW_DIR, "**", "*.pdf"), recursive=True))

    if not pdf_paths:
        print(f"{RAW_DIR} altinda PDF bulunamadi. Once 01_download_pdfs.py calistirin "
              f"ya da PDF'leri elle bu klasore kopyalayin.")
        return

    print(f"{len(pdf_paths)} PDF bulundu.")
    for i, pdf_path in enumerate(pdf_paths, 1):
        base = os.path.splitext(os.path.basename(pdf_path))[0]
        year_guess = os.path.basename(os.path.dirname(pdf_path))
        print(f"[{i}/{len(pdf_paths)}] isleniyor: {pdf_path}")

        pages, method = extract_pdf(pdf_path)
        if not pages:
            print("  UYARI: metin cikarilamadi (taranmis/gorsel PDF olabilir, OCR gerekebilir).")
            continue

        full_text = "\n\n".join(p for p in pages if p.strip())

        txt_path = os.path.join(OUT_DIR, f"{base}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        json_path = os.path.join(OUT_DIR, f"{base}.json")
        record = {
            "source_file": os.path.basename(pdf_path),
            "year": year_guess,
            "extraction_method": method,
            "num_pages": len(pages),
            "pages": pages,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        print(f"  -> {txt_path} ({len(full_text)} karakter)")

    print("Bitti.")


if __name__ == "__main__":
    main()
