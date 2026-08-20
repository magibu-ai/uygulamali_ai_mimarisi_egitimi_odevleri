"""Cevap normalizasyon yardımcıları (MIHENK Bölüm 8 puanlama kuralları).

Kısa cevaplı sorularda cevaplar; küçük harfe çevrilir, aksan/noktalama/fazla
boşluk normalize edilir, sonra kanonik cevap veya eş anlamlı varyasyonlarla
karşılaştırılır. Sayısal cevaplarda tolerans uygulanır.
"""
from __future__ import annotations

import re
import unicodedata

# Türkçe'ye özgü küçük-harf haritası (I/İ sorunu)
_TR_LOWER = str.maketrans({"I": "ı", "İ": "i", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})


def tr_lower(text: str) -> str:
    return text.translate(_TR_LOWER).lower()


def normalize_text(text: str) -> str:
    """Metni karşılaştırma için kanonik biçime indirger."""
    if text is None:
        return ""
    text = tr_lower(str(text))
    # Unicode uyumluluk normalizasyonu
    text = unicodedata.normalize("NFKC", text)
    # Noktalamayı boşlukla değiştir, harf/rakam/boşluk bırak
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    # Fazla boşlukları tek boşluğa indir
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_count(text: str) -> int:
    text = (text or "").strip()
    return len(text.split()) if text else 0


_NUM_RE = re.compile(r"^[-+]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?$|^[-+]?\d+(?:[.,]\d+)?$")


def try_parse_number(text: str):
    """'1.234,5' / '1,234.5' / '3.14' gibi biçimleri floata çevirmeyi dener."""
    if text is None:
        return None
    s = str(text).strip()
    if not _NUM_RE.match(s):
        # basit tek sayı denemesi
        s2 = re.sub(r"[^\d.,\-+]", "", s)
        if not s2 or not re.search(r"\d", s2):
            return None
        s = s2
    # Binlik/ondalık ayırıcı sezgisi
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,5 -> Avrupa
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.5 -> ABD
            s = s.replace(",", "")
    elif "," in s:
        # tek virgül: ondalık kabul et
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def numbers_match(a: str, b: str, rel_tol: float = 1e-3, abs_tol: float = 1e-6) -> bool:
    na, nb = try_parse_number(a), try_parse_number(b)
    if na is None or nb is None:
        return False
    return abs(na - nb) <= max(abs_tol, rel_tol * max(abs(na), abs(nb)))
