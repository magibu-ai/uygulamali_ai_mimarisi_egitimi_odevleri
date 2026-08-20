import logging
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)
TEMEL = "https://ec.europa.eu/esco/api"


def _al(yol, parametreler):
    try:
        cevap = requests.get(TEMEL + yol, params=parametreler, timeout=15)
        cevap.raise_for_status()
        return cevap.json()
    except (requests.RequestException, ValueError):
        logger.warning("ESCO istegi basarisiz: %s", yol)
        return None


def _meslek_uri(terim):
    veri = _al("/search", {"text": terim, "language": "en", "type": "occupation", "limit": 5})
    sonuclar = (veri or {}).get("_embedded", {}).get("results", [])
    if not sonuclar:
        return None
    # Once tam baslik eslesmesini ara; yoksa ilk (en alakali) sonucu al.
    for s in sonuclar:
        if (s.get("title") or "").strip().lower() == terim.strip().lower():
            return s.get("uri")
    return sonuclar[0].get("uri")


@lru_cache(maxsize=128)
def meslek_bilgisi(terim):
    """ESCO'dan (Avrupa) meslek tanimi + temel beceriler. Bulunamazsa None."""
    uri = _meslek_uri(terim)
    if not uri:
        return None
    veri = _al("/resource/occupation", {"uri": uri, "language": "en"})
    if not veri:
        return None
    tanim = (veri.get("description") or {}).get("en", {}).get("literal")
    beceriler = [
        s.get("title")
        for s in veri.get("_links", {}).get("hasEssentialSkill", [])
        if s.get("title")
    ][:8]
    if not tanim and not beceriler:
        return None
    return {"tanim": tanim, "beceriler": beceriler}
