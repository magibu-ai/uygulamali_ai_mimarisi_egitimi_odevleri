import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
API_ANAHTARI = os.getenv("ONET_API_KEY")
TEMEL = "https://api-v2.onetcenter.org"
BASLIK = {"X-API-Key": API_ANAHTARI, "Accept": "application/json"}


def _al(yol):
    try:
        cevap = requests.get(TEMEL + yol, headers=BASLIK, timeout=15)
        cevap.raise_for_status()
        return cevap.json()
    except (requests.RequestException, ValueError):
        logger.warning("O*NET istegi basarisiz: %s", yol)
        return None


def ne_yapar(soc):
    genel = _al(f"/online/occupations/{soc}")
    gorevler = _al(f"/online/occupations/{soc}/summary/tasks")
    aciklama = (genel or {}).get("description", "")
    liste = [g["title"] for g in (gorevler or {}).get("task", [])][:6]
    if not aciklama and not liste:
        return None
    return {"aciklama": aciklama, "gorevler": liste}


def nasil_baslanir(soc):
    jz = _al(f"/online/occupations/{soc}/summary/job_zone")
    egitim = _al(f"/online/occupations/{soc}/summary/education")
    if not jz and not egitim:
        return None
    dagilim = [
        {"seviye": e.get("title"), "yuzde": e.get("percentage_of_respondents")}
        for e in (egitim or {}).get("response", [])
    ][:3]
    return {
        "hazirlik_seviyesi": (jz or {}).get("title", ""),
        "egitim_notu": (jz or {}).get("education", ""),
        "deneyim_notu": (jz or {}).get("related_experience", ""),
        "egitim_dagilimi": dagilim,
    }


def buyume_gorunumu(soc):
    genel = _al(f"/online/occupations/{soc}")
    if genel is None:
        return None
    etiketler = genel.get("tags") or {}
    return {"parlak_gelecek": bool(etiketler.get("bright_outlook"))}


def beceriler(soc):
    veri = _al(f"/online/occupations/{soc}/summary/skills")
    if not veri:
        return None
    ogeler = veri.get("element") or veri.get("skill") or veri.get("response") or []
    liste = [o.get("name") or o.get("title") for o in ogeler if o.get("name") or o.get("title")][:6]
    if not liste:
        return None
    return {"beceriler": liste}
