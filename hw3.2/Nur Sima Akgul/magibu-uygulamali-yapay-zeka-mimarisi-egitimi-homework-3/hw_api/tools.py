"""
Tool (fonksiyon) katmani.
- DB tool'lari: db.py'yi kullanir (gercek okuma/yazma).
- Web tool'u: Google Books API'den kitap konusunu ceker (DB'de olmayan uzun bilgi).
- TOOLS: modele verilecek JSON semalari (OpenAI/Groq uyumlu).
- TOOL_FUNCS: isim -> fonksiyon eslemesi.
Tum cevaplar gercek veriye dayanir; hicbir fonksiyon bilgi uydurmaz.
"""
import requests
import db

db.init_db()  # ilk calismada tablolari kurar


# ---------- DB TABANLI TOOL'LAR ----------
def kitap_ara(sorgu: str) -> dict:
    """Baslik veya yazara gore kitap arar, durumunu doner."""
    sonuc = db.kitap_ara_db(sorgu)
    if not sonuc:
        return {"bulundu": False, "mesaj": f"'{sorgu}' ile eslesen kitap bulunamadi."}
    kitaplar = []
    for k in sonuc:
        item = {"id": k["id"], "baslik": k["baslik"], "yazar": k["yazar"],
                "tur": k["tur"], "sayfa": k["sayfa"], "durum": k["durum"]}
        if k["durum"] == "oduncte":
            item["teslim_tarih"] = k["teslim_tarih"]
        kitaplar.append(item)
    return {"bulundu": True, "adet": len(kitaplar), "kitaplar": kitaplar}


def kitap_oner(tur: str, koken: str = None, max_sayfa: int = None, min_sayfa: int = None) -> dict:
    """Belirtilen tur ve filtrelere gore kutuphanedeki (bosta) kitaplari onerir."""
    sonuc = db.oneri_db(tur=tur, koken=koken, max_sayfa=max_sayfa,
                        min_sayfa=min_sayfa, sadece_bosta=True)
    if not sonuc:
        return {"bulundu": False,
                "mesaj": f"Bu kriterlere uygun bosta kitap yok (tur={tur})."}
    oneriler = [{"id": k["id"], "baslik": k["baslik"], "yazar": k["yazar"],
                 "sayfa": k["sayfa"], "koken": k["koken"]} for k in sonuc[:6]]
    return {"bulundu": True, "adet": len(oneriler), "oneriler": oneriler}


def kitap_odunc_al(kitap_id: int, okuyucu: str) -> dict:
    """Bosta olan bir kitabi okuyucuya odunc verir; 2 hafta teslim tarihi atar."""
    r = db.odunc_al_db(int(kitap_id), okuyucu)
    k = db.kitap_getir(int(kitap_id))
    baslik = k["baslik"] if k else f"#{kitap_id}"
    if not r["ok"]:
        cevap = {"basarili": False, "kitap": baslik, "mesaj": r["hata"]}
        if r.get("teslim_tarih"):
            cevap["en_gec_teslim"] = r["teslim_tarih"]
        return cevap
    return {"basarili": True, "kitap": baslik, "okuyucu": okuyucu,
            "odunc_tarih": r["odunc_tarih"], "en_gec_teslim": r["teslim_tarih"],
            "mesaj": f"'{baslik}' odunc verildi. En gec {r['teslim_tarih']} tarihinde teslim edilmelidir."}


def kitap_iade_et(kitap_id: int) -> dict:
    """Oduncteki kitabi iade alir; erken/zamaninda/gec durumunu kaydeder."""
    r = db.iade_et_db(int(kitap_id))
    k = db.kitap_getir(int(kitap_id))
    baslik = k["baslik"] if k else f"#{kitap_id}"
    if not r["ok"]:
        return {"basarili": False, "kitap": baslik, "mesaj": r["hata"]}
    aciklama = {"erken": "teslim tarihinden once", "zamaninda": "tam zamaninda",
                "gec": "teslim tarihinden sonra"}[r["durum_notu"]]
    return {"basarili": True, "kitap": baslik, "durum_notu": r["durum_notu"],
            "mesaj": f"'{baslik}' iade alindi ({aciklama})."}


def odunc_durumu(sorgu: str) -> dict:
    """Bir kitabin su an oduncte olup olmadigini ve en gec teslim tarihini soyler."""
    sonuc = db.kitap_ara_db(sorgu)
    if not sonuc:
        return {"bulundu": False, "mesaj": f"'{sorgu}' bulunamadi."}
    k = sonuc[0]
    if k["durum"] == "bosta":
        return {"bulundu": True, "kitap": k["baslik"], "durum": "bosta",
                "mesaj": f"'{k['baslik']}' su an kutuphanede, hemen odunc alabilirsiniz."}
    return {"bulundu": True, "kitap": k["baslik"], "durum": "oduncte",
            "en_gec_teslim": k["teslim_tarih"],
            "mesaj": f"'{k['baslik']}' su an baska bir okuyucuda. En gec {k['teslim_tarih']} tarihinde iade edilecek."}


# ---------- WEB TABANLI TOOL ----------
def _wikipedia_ozet(baslik: str):
    """Turkce Wikipedia'dan kitabin ozetini ceker (comert limit, guvenilir)."""
    try:
        # once arama yapip dogru sayfa basligini bul
        s = requests.get("https://tr.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": f"{baslik} kitap roman",
            "format": "json", "srlimit": 1,
        }, headers={"User-Agent": "KutuphaneAsistani/1.0"}, timeout=15)
        s.raise_for_status()
        hits = s.json().get("query", {}).get("search", [])
        if not hits:
            return None
        sayfa = hits[0]["title"]
        # sayfanin ozet (intro) metnini al
        e = requests.get("https://tr.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
            "titles": sayfa, "format": "json",
        }, headers={"User-Agent": "KutuphaneAsistani/1.0"}, timeout=15)
        e.raise_for_status()
        pages = e.json().get("query", {}).get("pages", {})
        for _, p in pages.items():
            ozet = p.get("extract")
            if ozet and len(ozet) > 40:
                return {"kitap": sayfa, "konu": ozet[:600]}
        return None
    except Exception:
        return None


def _googlebooks_ozet(baslik: str):
    """Google Books'tan ozet (yedek kaynak)."""
    try:
        r = requests.get("https://www.googleapis.com/books/v1/volumes",
                         params={"q": baslik, "maxResults": 3}, timeout=15)
        r.raise_for_status()
        for it in r.json().get("items", []):
            vi = it.get("volumeInfo", {})
            if vi.get("description"):
                return {"kitap": vi.get("title", baslik), "konu": vi["description"][:600]}
        return None
    except Exception:
        return None


def kitap_konusu(baslik: str) -> dict:
    """Kitabin konusunu internetten ceker (DB'de tutulmayan uzun bilgi).
    Once Turkce Wikipedia, olmazsa Google Books denenir."""
    for kaynak in (_wikipedia_ozet, _googlebooks_ozet):
        sonuc = kaynak(baslik)
        if sonuc:
            return {"bulundu": True, "kitap": sonuc["kitap"], "konu": sonuc["konu"]}
    return {"bulundu": False,
            "mesaj": f"'{baslik}' icin cevrimici bir konu ozeti bulunamadi."}


# ---------- JSON SEMALARI (model icin) ----------
TOOLS = [
    {"type": "function", "function": {
        "name": "kitap_ara",
        "description": "Baslik veya yazar adina gore kutuphanede kitap arar ve durumunu (bosta/oduncte) doner.",
        "parameters": {"type": "object", "properties": {
            "sorgu": {"type": "string", "description": "Kitap basligi ya da yazar adi"}},
            "required": ["sorgu"]}}},
    {"type": "function", "function": {
        "name": "kitap_oner",
        "description": "Belirtilen turde ve filtrelerde (koken, sayfa) kutuphanedeki bosta kitaplari onerir.",
        "parameters": {"type": "object", "properties": {
            "tur": {"type": "string", "description": "Kitap turu (orn: polisiye, roman, bilim kurgu, cocuk)"},
            "koken": {"type": "string", "description": "'yerli' ya da 'yabanci' (istege bagli)"},
            "max_sayfa": {"type": "integer", "description": "En fazla sayfa sayisi (ince kitap icin)"},
            "min_sayfa": {"type": "integer", "description": "En az sayfa sayisi (kalin kitap icin)"}},
            "required": ["tur"]}}},
    {"type": "function", "function": {
        "name": "kitap_odunc_al",
        "description": "Bosta olan bir kitabi bir okuyucuya odunc verir ve 2 hafta sonrasina teslim tarihi atar.",
        "parameters": {"type": "object", "properties": {
            "kitap_id": {"type": "integer", "description": "Odunc alinacak kitabin id'si (once kitap_ara ile bul)"},
            "okuyucu": {"type": "string", "description": "Okuyucunun adi"}},
            "required": ["kitap_id", "okuyucu"]}}},
    {"type": "function", "function": {
        "name": "kitap_iade_et",
        "description": "Oduncte olan bir kitabi iade alir ve erken/zamaninda/gec durumunu kaydeder.",
        "parameters": {"type": "object", "properties": {
            "kitap_id": {"type": "integer", "description": "Iade edilecek kitabin id'si"}},
            "required": ["kitap_id"]}}},
    {"type": "function", "function": {
        "name": "odunc_durumu",
        "description": "Bir kitabin su an oduncte olup olmadigini ve en gec teslim tarihini bildirir.",
        "parameters": {"type": "object", "properties": {
            "sorgu": {"type": "string", "description": "Kitap basligi"}},
            "required": ["sorgu"]}}},
    {"type": "function", "function": {
        "name": "kitap_konusu",
        "description": "Bir kitabin konusunu/ozetini internetten (Google Books) getirir. Kutuphane veritabaninda konu ozeti tutulmadigi icin bu bilgi web'den alinir.",
        "parameters": {"type": "object", "properties": {
            "baslik": {"type": "string", "description": "Konusu ogrenilecek kitabin basligi"}},
            "required": ["baslik"]}}},
]

TOOL_FUNCS = {
    "kitap_ara": kitap_ara,
    "kitap_oner": kitap_oner,
    "kitap_odunc_al": kitap_odunc_al,
    "kitap_iade_et": kitap_iade_et,
    "odunc_durumu": odunc_durumu,
    "kitap_konusu": kitap_konusu,
}