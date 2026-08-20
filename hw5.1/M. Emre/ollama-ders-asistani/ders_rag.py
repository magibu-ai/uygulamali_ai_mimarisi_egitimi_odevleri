"""Ders kitaplari uzerinde RAG: parcalama, vektor arama ve topraklanmis cevap.

Amac tek: model yalnizca ders kitaplarinda yazani soylesin. Bunu iki kapi saglar.

    1. ARAMA KAPISI   -> benzerlik esigin altindaysa LLM hic cagrilmaz.
    2. URETIM KAPISI  -> LLM'e "sadece bu metinlerden cevapla" talimati verilir.

Ikisinden biri gecilemezse cevap sabit bir reddetme cumlesi olur. Boylece model,
kendi genel bilgisiyle ders kitabinda olmayan bir sey uyduramaz.
"""

from __future__ import annotations

import os
import re

import chromadb
import torch
from sentence_transformers import SentenceTransformer

import ollama_client

KOK = os.path.dirname(os.path.abspath(__file__))
DB_YOLU = os.path.join(KOK, "chroma_db")
VERI_YOLU = os.path.join(KOK, "veri")

# Turkce'ye ozel, 768 boyutlu, 8192 token baglam penceresi olan hafif model.
EMBED_MODELI = "magibu/embeddingmagibu-200m"
KOLEKSIYON = "ders_kitaplari"

# Bir parcanin "alakali" sayilmasi icin gereken en dusuk kosinus benzerligi.
# esik_kalibrasyon.py ile olculerek secildi.
ESIK = 0.45

RET = "Bilmiyorum — bu bilgi ders kitaplarinda bulunmuyor."

SISTEM_ISTEMI = f"""Sen bir ders calisma asistanisin.

Kurallar:
1. SADECE asagida verilen ders kitabi parcalarindaki bilgiyi kullan.
2. Genel bilgini KESINLIKLE kullanma. Metinde yoksa, senin icin yoktur.
3. Parcalar soruyu cevaplamaya yetmiyorsa aynen su cumleyi yaz, baska hicbir sey ekleme:
{RET}
4. Cevabini Turkce, kisa ve ogrenciye anlatir gibi yaz.
5. Hangi dersten geldigini belirt (fizik / kimya / tarih).
"""

# --- Parcalama ayarlari -------------------------------------------------------
HEDEF = 800  # karakter
ORTUSME = 150
EN_KISA = 120
CUMLE_SINIRI = re.compile(r"(?<=[.!?:])\s+")

_model: SentenceTransformer | None = None


def cihaz() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def embed_modeli() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODELI, device=cihaz())
    return _model


def vektorlestir(metinler: list[str], ilerleme: bool = False):
    """Metinleri birim uzunluga normalize edilmis vektorlere cevirir.

    Normalize edildigi icin nokta carpimi dogrudan kosinus benzerligine esittir;
    Chroma'nin mesafe hesabi ile raporlanan skorlar boylece tutarli kalir.
    """
    return embed_modeli().encode(
        metinler,
        batch_size=64,
        show_progress_bar=ilerleme,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )


# --- Parcalama ----------------------------------------------------------------


def _birimlere_ayir(metin: str) -> list[str]:
    """Metni dogal sinirlarindan (once satir, sonra cumle) bolunebilir birimlere ayirir."""
    birimler: list[str] = []
    for satir in metin.split("\n"):
        satir = satir.strip()
        if not satir:
            continue
        if len(satir) <= HEDEF:
            birimler.append(satir)
            continue
        parca = ""
        for cumle in CUMLE_SINIRI.split(satir):
            if len(parca) + len(cumle) + 1 <= HEDEF:
                parca = f"{parca} {cumle}".strip()
            else:
                if parca:
                    birimler.append(parca)
                parca = cumle
        if parca:
            birimler.append(parca)
    return birimler


def _kuyruk(metin: str, uzunluk: int) -> str:
    if len(metin) <= uzunluk:
        return metin
    kesit = metin[-uzunluk:]
    parcalar = CUMLE_SINIRI.split(kesit, maxsplit=1)
    return parcalar[-1].strip() if len(parcalar) > 1 else kesit.strip()


def parcala(metin: str) -> list[str]:
    """Metni ortusmeli parcalara boler.

    Ders kitabi metinlerinde `\\n\\n` ayraci yok; her satir bir cumle. Bu yuzden
    saf paragraf bolme uygulanamiyor. Saf token bolme ise cumleyi ortasindan
    keserek tanimlari yarim birakiyor. Karma yontem: once dogal sinirlardan
    birimlere ayir, sonra hedef uzunluga kadar birlestir.
    """
    if not metin or not metin.strip():
        return []

    parcalar: list[str] = []
    aktif = ""
    for birim in _birimlere_ayir(metin):
        aday = f"{aktif} {birim}".strip() if aktif else birim
        if len(aday) <= HEDEF:
            aktif = aday
            continue
        if aktif:
            parcalar.append(aktif)
            bas = _kuyruk(aktif, ORTUSME)
            aktif = f"{bas} {birim}".strip() if bas else birim
        else:
            aktif = birim
    if aktif:
        parcalar.append(aktif)

    temiz: list[str] = []
    for p in parcalar:
        if temiz and len(p) < EN_KISA:
            temiz[-1] = f"{temiz[-1]} {p}"
        else:
            temiz.append(p)
    return temiz


# --- Vektor veritabani --------------------------------------------------------


def koleksiyon(sifirla: bool = False):
    istemci = chromadb.PersistentClient(path=DB_YOLU)
    if sifirla:
        try:
            istemci.delete_collection(KOLEKSIYON)
        except Exception:
            pass
    return istemci.get_or_create_collection(
        name=KOLEKSIYON,
        metadata={"hnsw:space": "cosine"},  # mesafe = 1 - kosinus benzerligi
        embedding_function=None,  # vektorleri disaridan veriyoruz
    )


def ara(soru: str, k: int = 4, ders: str | None = None) -> list[dict]:
    """Soruyu vektore cevirip en yakin k parcayi getirir.

    ders verilirse arama yalnizca o kitapla sinirlanir (metadata filtresi).
    """
    kol = koleksiyon()
    if kol.count() == 0:
        return []

    vektor = vektorlestir([soru])[0]
    sonuc = kol.query(
        query_embeddings=[vektor.tolist()],
        n_results=min(k, kol.count()),
        where={"ders": ders} if ders else None,
        include=["documents", "metadatas", "distances"],
    )

    bulunanlar = []
    for metin, meta, uzaklik in zip(
        sonuc["documents"][0], sonuc["metadatas"][0], sonuc["distances"][0]
    ):
        bulunanlar.append(
            {
                "metin": metin,
                "ders": meta.get("ders", "-"),
                "parca_no": meta.get("parca_no"),
                "benzerlik": 1.0 - float(uzaklik),
            }
        )
    return bulunanlar


def cevapla(soru: str, k: int = 4, ders: str | None = None) -> dict:
    """Ders sorusunu yalnizca indekslenmis kitap parcalarina dayanarak cevaplar."""
    bulunanlar = ara(soru, k=k, ders=ders)

    # 1. KAPI — arama. Hicbir parca esigi gecmediyse LLM hic cagrilmaz.
    alakalilar = [b for b in bulunanlar if b["benzerlik"] >= ESIK]
    if not alakalilar:
        en_iyi = bulunanlar[0]["benzerlik"] if bulunanlar else 0.0
        return {"cevap": RET, "kaynaklar": [], "topraklandi": False, "en_yuksek_skor": en_iyi}

    # 2. KAPI — uretim. Model yalnizca bu parcalardan cevaplamakla yukumlu.
    baglam = "\n\n".join(
        f"[{i}] ({b['ders']}) {b['metin']}" for i, b in enumerate(alakalilar, start=1)
    )
    mesaj = ollama_client.chat(
        messages=[
            {"role": "system", "content": SISTEM_ISTEMI},
            {"role": "user", "content": f"DERS KITABI PARCALARI:\n{baglam}\n\nSORU: {soru}"},
        ],
        temperature=0.0,  # yaraticilik yok, metne sadakat
    )
    cevap = (mesaj.get("content") or "").strip() or RET
    topraklandi = "bilmiyorum" not in cevap.lower()[:40]

    kaynaklar = []
    if topraklandi:
        gorulen = set()
        for b in alakalilar:
            anahtar = (b["ders"], b["parca_no"])
            if anahtar not in gorulen:
                gorulen.add(anahtar)
                kaynaklar.append(
                    {
                        "ders": b["ders"],
                        "parca_no": b["parca_no"],
                        "benzerlik": round(b["benzerlik"], 3),
                    }
                )

    return {
        "cevap": cevap,
        "kaynaklar": kaynaklar,
        "topraklandi": topraklandi,
        "en_yuksek_skor": round(alakalilar[0]["benzerlik"], 3),
    }
