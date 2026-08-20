"""Akupunktur asistani araclari ve deterministik guvenlik freni."""

import json

import rag

RED_FLAGS = (
    "ani guc kaybi", "yuzde kayma", "konusma bozuklugu", "bilinc kaybi",
    "siddetli gogus agrisi", "nefes alamama", "kontrolsuz kanama", "anafilaksi",
)
# ponytail: Bu kisa liste triyaj sistemi degildir; klinik kullanim oncesi kurumun
# onayli kirmizi bayrak protokoluyle degistirilmelidir.


def kirmizi_bayrak_var(text: str) -> bool:
    normalized = text.casefold().translate(str.maketrans("çğıöşü", "cgiosu"))
    return any(flag in normalized for flag in RED_FLAGS)


def _results(query: str, k: int) -> str:
    hits = rag.search(query, k)
    for hit in hits:
        hit["page_image"] = rag.render_page(hit["pdf_page"])
    return json.dumps(hits, ensure_ascii=False)


def kitapta_ara(sorgu: str, sonuc_sayisi: int = 5) -> str:
    """Ingilizce kitapta semptom, muayene bulgusu veya TCM paterni arar."""
    return _results(sorgu, min(max(sonuc_sayisi, 1), 8))


def nokta_bilgisi_getir(nokta_kodu: str) -> str:
    """Bir akupunktur noktasinin kitaptaki konum, islev ve uyari bilgilerini arar."""
    code = nokta_kodu.strip().upper()
    channel, _, number = code.replace(" ", "").partition("-")
    channel = {"GV": "DU", "LV": "LIV", "LI": "L.I.", "GB": "G.B."}.get(channel, channel)
    book_code = f"{channel}-{number}"
    result = rag.collection().get(
        where_document={"$contains": book_code}, include=["documents", "metadatas"]
    )
    hits = [
        {"text": text, **meta, "similarity": 1.0}
        for text, meta in zip(result["documents"], result["metadatas"])
    ]
    def heading_score(hit: dict) -> tuple[bool, bool]:
        code_at = hit["text"].find(book_code)
        location_at = hit["text"].find("Location", code_at)
        return (code_at >= 0 and 0 <= location_at - code_at < 180,
                hit.get("book_page") != "on/arka kisim")

    hits.sort(key=heading_score, reverse=True)
    if hits:
        primary = hits[0]
        hits = [primary] + [h for h in hits[1:] if h["pdf_page"] == primary["pdf_page"]][:1]
    if not hits:
        return json.dumps({"error": f"{code} kitapta tam kod eşleşmesiyle bulunamadı."}, ensure_ascii=False)
    for hit in hits:
        hit["page_image"] = rag.render_page(hit["pdf_page"])
    return json.dumps(hits, ensure_ascii=False)


TOOLS = {"kitapta_ara": kitapta_ara, "nokta_bilgisi_getir": nokta_bilgisi_getir}
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "kitapta_ara",
            "description": "Vakayla ilgili TCM paternlerini İngilizce Maciocia kitabında arar. Sorguyu İngilizce yaz.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Kısa İngilizce arama sorgusu"},
                    "sonuc_sayisi": {"type": "integer", "description": "1-8 arası sonuç sayısı"},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nokta_bilgisi_getir",
            "description": "Aday bir akupunktur noktasının kitaptaki bilgilerini doğrular.",
            "parameters": {
                "type": "object",
                "properties": {"nokta_kodu": {"type": "string", "description": "Örnek: LI-4"}},
                "required": ["nokta_kodu"],
            },
        },
    },
]


if __name__ == "__main__":
    assert kirmizi_bayrak_var("Ani güç kaybı ve yüzde kayma var")
    assert not kirmizi_bayrak_var("Üç gündür hafif baş ağrısı var")
    assert rag.chunk_text(" ".join(map(str, range(520))))
    print("Temel kontroller geçti.")
