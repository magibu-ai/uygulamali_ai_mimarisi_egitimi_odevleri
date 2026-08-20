import subprocess
import sys
import xml.etree.ElementTree as ET

import httpx
from ddgs import DDGS

GITHUB_TOKEN = None  # app.py .env'i yukledikten sonra doldurur

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def web_ara(sorgu, max_sonuc=5):
    """DuckDuckGo ile genel web aramasi yapar (anahtarsiz)."""
    try:
        sonuclar = DDGS().text(sorgu, max_results=int(max_sonuc))
        if not sonuclar:
            return {"hata": f"'{sorgu}' icin web sonucu bulunamadi."}
        return {
            "sorgu": sorgu,
            "sonuclar": [
                {"baslik": s.get("title"), "ozet": s.get("body"), "link": s.get("href")}
                for s in sonuclar
            ],
        }
    except Exception as e:
        return {"hata": f"Web aramasi basarisiz: {e}"}


def huggingface_ara(sorgu, sirala="downloads", limit=5):
    """Hugging Face Hub'da modelleri arar, indirme/begeni sayisi ve etiketlerle doner."""
    try:
        yanit = httpx.get(
            "https://huggingface.co/api/models",
            params={"search": sorgu, "sort": sirala, "direction": -1, "limit": int(limit)},
            timeout=15,
        )
        yanit.raise_for_status()
        modeller = yanit.json()
        if not modeller:
            return {"hata": f"'{sorgu}' icin Hugging Face'te model bulunamadi."}
        return {
            "sorgu": sorgu,
            "modeller": [
                {
                    "id": m.get("id"),
                    "indirme": m.get("downloads"),
                    "begeni": m.get("likes"),
                    "etiketler": (m.get("tags") or [])[:8],
                    "son_guncelleme": m.get("lastModified"),
                    "link": f"https://huggingface.co/{m.get('id')}",
                }
                for m in modeller
            ],
        }
    except Exception as e:
        return {"hata": f"Hugging Face aramasi basarisiz: {e}"}


def arxiv_ara(sorgu, max_sonuc=5):
    """arXiv'de makale arar, baslik/ozet/yazar/PDF linki doner (anahtarsiz)."""
    try:
        yanit = httpx.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{sorgu}",
                "start": 0,
                "max_results": int(max_sonuc),
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            timeout=15, follow_redirects=True,
        )
        yanit.raise_for_status()
        kok = ET.fromstring(yanit.text)
        girdiler = kok.findall("atom:entry", ARXIV_NS)
        if not girdiler:
            return {"hata": f"'{sorgu}' icin arXiv'te makale bulunamadi."}

        makaleler = []
        for g in girdiler:
            baslik = (g.findtext("atom:title", default="", namespaces=ARXIV_NS) or "").strip()
            ozet = (g.findtext("atom:summary", default="", namespaces=ARXIV_NS) or "").strip()
            if len(ozet) > 500:
                ozet = ozet[:500].rsplit(" ", 1)[0] + "..."
            yazarlar = [
                a.findtext("atom:name", default="", namespaces=ARXIV_NS)
                for a in g.findall("atom:author", ARXIV_NS)
            ]
            link = next(
                (l.get("href") for l in g.findall("atom:link", ARXIV_NS) if l.get("title") == "pdf"),
                g.findtext("atom:id", default="", namespaces=ARXIV_NS),
            )
            makaleler.append({
                "baslik": baslik,
                "yazarlar": yazarlar,
                "ozet": ozet,
                "yayin_tarihi": g.findtext("atom:published", default="", namespaces=ARXIV_NS),
                "pdf_link": link,
            })
        return {"sorgu": sorgu, "makaleler": makaleler}
    except Exception as e:
        return {"hata": f"arXiv aramasi basarisiz: {e}"}


def github_ara(sorgu, max_sonuc=5):
    """GitHub'da repo arar, yildiz/dil/aciklama ile doner. Opsiyonel GITHUB_TOKEN rate-limit'i iyilestirir."""
    try:
        basliklar = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            basliklar["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        yanit = httpx.get(
            "https://api.github.com/search/repositories",
            params={"q": sorgu, "sort": "stars", "order": "desc", "per_page": int(max_sonuc)},
            headers=basliklar, timeout=15,
        )
        yanit.raise_for_status()
        veri = yanit.json()
        repolar = veri.get("items", [])
        if not repolar:
            return {"hata": f"'{sorgu}' icin GitHub'da repo bulunamadi."}
        return {
            "sorgu": sorgu,
            "repolar": [
                {
                    "ad": r.get("full_name"),
                    "aciklama": r.get("description"),
                    "yildiz": r.get("stargazers_count"),
                    "dil": r.get("language"),
                    "link": r.get("html_url"),
                }
                for r in repolar
            ],
        }
    except Exception as e:
        return {"hata": f"GitHub aramasi basarisiz: {e}"}


def kod_calistir(kod, zaman_asimi=10):
    """Kucuk bir Python kod parcasini yerel altprocess'te calistirir (egitim amacli, tam sandbox degildir)."""
    try:
        sonuc = subprocess.run(
            [sys.executable, "-c", kod],
            capture_output=True, text=True, timeout=int(zaman_asimi),
        )
        cikti = sonuc.stdout
        hata = sonuc.stderr
        if len(cikti) > 2000:
            cikti = cikti[:2000] + "\n... (kisaltildi)"
        if len(hata) > 1000:
            hata = hata[:1000] + "\n... (kisaltildi)"
        return {"stdout": cikti, "stderr": hata, "donus_kodu": sonuc.returncode}
    except subprocess.TimeoutExpired:
        return {"hata": f"Kod {zaman_asimi} saniyede tamamlanmadi (zaman asimi)."}
    except Exception as e:
        return {"hata": f"Kod calistirilamadi: {e}"}


def artifact_goster(baslik, html):
    """Kullaniciya interaktif bir HTML/JS paneli (plan, tablo, kart vb.) gostermek/guncellemek icin cagirilir."""
    if not html or not html.strip():
        return {"hata": "html icerigi bos olamaz."}
    if len(html) > 50000:
        return {"hata": "html cok uzun (50000 karakteri asamaz), kisalt."}
    return {"durum": "gosterildi", "baslik": baslik or "Panel", "html": html}


ARAC_FONKSIYONLARI = {
    "web_ara": web_ara,
    "huggingface_ara": huggingface_ara,
    "arxiv_ara": arxiv_ara,
    "github_ara": github_ara,
    "kod_calistir": kod_calistir,
    "artifact_goster": artifact_goster,
}

ARAC_SEMALARI = [
    {
        "type": "function",
        "function": {
            "name": "web_ara",
            "description": "Genel bir konuyu DuckDuckGo ile webde arar. Guncel haber/blog/duyuru gibi genel baglam icin kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Arama sorgusu, orn: 'kucuk dil modelleri 2025'"},
                    "max_sonuc": {"type": "integer", "description": "Kac sonuc getirilecek, varsayilan 5"},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "huggingface_ara",
            "description": "Hugging Face Hub'da bir alanla ilgili modelleri arar; indirme sayisi, etiketler ve model karti linkiyle doner. Kullanici 'guncel modeller' isteyince bunu cagir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Arama sorgusu, orn: 'turkish llm'"},
                    "sirala": {"type": "string", "description": "downloads, likes veya trending; varsayilan downloads"},
                    "limit": {"type": "integer", "description": "Kac model getirilecek, varsayilan 5"},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "arxiv_ara",
            "description": "arXiv'de akademik makale arar; baslik, ozet, yazarlar ve PDF linkiyle doner. Kullanici 'makaleler/akademik calismalar' isteyince bunu cagir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Arama sorgusu, orn: 'retrieval augmented generation'"},
                    "max_sonuc": {"type": "integer", "description": "Kac makale getirilecek, varsayilan 5"},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_ara",
            "description": "GitHub'da orneklerin/uygulamalarin koduna bakmak icin repo arar; yildiz sayisi, dil ve linkle doner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Arama sorgusu, orn: 'llama.cpp finetune example'"},
                    "max_sonuc": {"type": "integer", "description": "Kac repo getirilecek, varsayilan 5"},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "artifact_goster",
            "description": (
                "Kullaniciya interaktif bir HTML/JS paneli gosterir. Format tamamen serbest: "
                "plan/checklist, karsilastirma tablosu, kart, SVG veya Canvas ile diyagram/cizim/"
                "grafik, basit interaktif bir JS bileseni — ne uygunsa onu uret, kendini kisitlama. "
                "Kullanici bir plan/liste/tablo/cizim gibi yapilandirilmis veya gorsel bir cikti "
                "isteyince ya da var olan paneli guncellemek gerektiginde bu araci cagir. html TAM "
                "ve KENDINE YETERLI olmali (inline <style>, <script>, <svg> serbest); harici CDN/"
                "script/resim URL'si veya ag istegi ICERMEMELI. Paneli guncellerken TAM icerigi "
                "yeniden yaz, parca/diff gonderme."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "baslik": {"type": "string", "description": "Panelin kisa basligi"},
                    "html": {"type": "string", "description": "Tam, kendine yeterli HTML icerigi"},
                },
                "required": ["baslik", "html"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kod_calistir",
            "description": "Kisa bir Python kod parcasini yerelde calistirip stdout/stderr sonucunu doner. Bulunan bir ornegi test etmek icin kullan; uzun surecek veya yikici islemler icin kullanma.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kod": {"type": "string", "description": "Calistirilacak Python kodu"},
                    "zaman_asimi": {"type": "integer", "description": "Saniye cinsinden zaman asimi, varsayilan 10"},
                },
                "required": ["kod"],
            },
        },
    },
]


def araci_calistir(ad, argumanlar):
    argumanlar = argumanlar or {}
    fonksiyon = ARAC_FONKSIYONLARI.get(ad)
    if fonksiyon is None:
        return {"hata": f"'{ad}' adinda bir arac yok."}
    try:
        return fonksiyon(**argumanlar)
    except TypeError as e:
        return {"hata": f"'{ad}' hatali argumanlarla cagrildi: {e}"}
