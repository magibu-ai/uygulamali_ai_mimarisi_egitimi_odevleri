"""Yerel, kural tabanlı MOCK LLM — API anahtarı olmadan geliştirme/test için.

Amaç: Gerçek modele erişim olmadan da tool-calling döngüsünün (agent + tools +
DB) uçtan uca çalışabilmesi. Bu sınıf, OpenAI Chat Completions istemcisinin
`client.chat.completions.create(...)` arayüzünü ve dönüş nesnesi şeklini
(`response.choices[0].message.tool_calls[...]`) birebir taklit eder; böylece
`src/llm.py` içindeki döngü HİÇ DEĞİŞMEDEN çalışır.

Model kararı basit niyet (intent) tespiti + bir durum makinesiyle verilir:
  - "öner / bul / film"      -> search_movies
  - "... ekle"               -> önce search_movies, sonra add_to_watchlist
  - "listem / neler var"     -> get_watchlist
Sonuç mesajları YALNIZCA tool çıktısındaki gerçek verilerden üretilir
(gerçek modeldeki halüsinasyon-engeli sözleşmesiyle aynı davranış).
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any, Optional

# Seed kataloğundaki türler + yaygın eş anlamlılar -> kanonik tür.
_GENRE_SYNONYMS = {
    "bilim kurgu": "Bilim Kurgu",
    "bilimkurgu": "Bilim Kurgu",
    "dram": "Dram",
    "suç": "Suç",
    "aksiyon": "Aksiyon",
    "fantastik": "Fantastik",
    "western": "Western",
    "animasyon": "Animasyon",
    "çizgi": "Animasyon",
    "romantik": "Romantik",
    "aşk": "Romantik",
    "tarih": "Tarih",
    "gerilim": "Gerilim",
    "korku": "Gerilim",
    "macera": "Macera",
    "komedi": "Komedi",
    "savaş": "Savaş",
}

_ADD_KEYWORDS = ("ekle", "ekler misin", "listeme kaydet")
_VIEW_KEYWORDS = ("listem", "listemde", "neler var", "izleme listesi", "watchlist", "ne var")

# Başlık ayıklarken atılacak dolgu kelimeler.
_STOPWORDS = {
    "film", "filmi", "filmini", "filmler", "filmleri", "öner", "önerir",
    "misin", "bana", "bir", "göster", "hangi", "hangileri", "en", "iyi",
    "neler", "var", "bul", "izle", "güzel", "tavsiye", "et", "eder", "lütfen",
    "için", "ver", "izleme", "listeme", "listemde", "listesine", "listesi",
    "ekle", "kaydet", "puanı", "üstü", "üzeri", "altı", "yıl", "yılında",
}


class MockClient:
    """OpenAI istemcisini taklit eden basit sarmalayıcı."""

    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(
        self,
        *,
        model: str = "",
        messages: Optional[list[dict[str, Any]]] = None,
        tools: Any = None,
        tool_choice: Any = None,
        temperature: Any = None,
        **kwargs: Any,
    ):
        """Bir sonraki adımı planlar ve OpenAI-uyumlu yanıt nesnesi döndürür."""
        plan = _plan(messages or [])
        if plan["type"] == "tool":
            return _tool_response(plan["name"], plan["arguments"], plan["call_index"])
        return _text_response(plan["content"])


# --------------------------------------------------------------------------- #
# Planlayıcı (durum makinesi)
# --------------------------------------------------------------------------- #
def _plan(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Mesaj geçmişine bakarak sıradaki eylemi (tool çağrısı ya da final) seçer."""
    last_user = _last_user_message(messages)
    text = (last_user or "").lower()

    # Bu turda şimdiye dek dönen tool sonuçları (son kullanıcı mesajından sonra).
    tool_steps = _tool_steps_since_user(messages)
    call_index = len(tool_steps) + 1

    is_add = any(k in text for k in _ADD_KEYWORDS)
    is_view = any(k in text for k in _VIEW_KEYWORDS)

    # 1) "Listeme ekle" akışı: search_movies -> add_to_watchlist -> final
    if is_add:
        if not tool_steps:
            title = _extract_title(text)
            return _tool("search_movies", {"query": title}, call_index)
        last_name, last_result = tool_steps[-1]
        if last_name == "search_movies":
            movies = last_result.get("movies", [])
            if not movies:
                return _final("Öyle bir filmi bulamadım, o yüzden ekleyemedim. Adını farklı yazmayı dener misin?")
            movie = movies[0]
            return _tool("add_to_watchlist", {"movie_id": movie["id"], "user": "guest"}, call_index)
        if last_name == "add_to_watchlist":
            if last_result.get("status") == "added":
                m = last_result["movie"]
                return _final(f"Tamamdır, '{m['title']}' ({m.get('year','')}) listene eklendi. İyi seyirler! 🍿")
            if last_result.get("status") == "already_exists":
                m = last_result["movie"]
                return _final(f"'{m['title']}' zaten listende duruyor. 🙂")
            return _final("Bunu ekleyemedim, çünkü öyle bir film elimde yok.")

    # 2) "Listemde ne var?" akışı: get_watchlist -> final
    if is_view:
        if not tool_steps:
            return _tool("get_watchlist", {"user": "guest"}, call_index)
        _, result = tool_steps[-1]
        items = result.get("items", [])
        if not items:
            return _final("Listen şu an bomboş. İstersen bir film önereyim, hemen ekleyelim.")
        satirlar = [f"- {it['title']} ({it.get('year','')}, puan {it.get('rating','')})" for it in items]
        return _final("Listende şunlar var:\n" + "\n".join(satirlar))

    # 3) Varsayılan: arama / öneri akışı: search_movies -> final
    if not tool_steps:
        return _tool("search_movies", _build_search_args(text), call_index)
    _, result = tool_steps[-1]
    movies = result.get("movies", [])
    if not movies:
        return _final("Bu tarife uyan bir şey çıkmadı. Başka bir tür ya da puan dener misin?")
    top = movies[:3]
    satirlar = [
        f"- {m['title']} ({m.get('year','')}, puan {m.get('rating','')}, yön. {m.get('director','')})"
        for m in top
    ]
    return _final("Şunlar tam senlik olabilir:\n" + "\n".join(satirlar))


# --------------------------------------------------------------------------- #
# Niyet/argüman ayıklama yardımcıları
# --------------------------------------------------------------------------- #
def _build_search_args(text: str) -> dict[str, Any]:
    """Serbest metinden search_movies argümanlarını çıkarır."""
    args: dict[str, Any] = {}

    genre = _detect_genre(text)
    if genre:
        args["genre"] = genre

    rating = _detect_rating(text)
    if rating is not None:
        args["min_rating"] = rating

    year = _detect_year(text)
    if year is not None:
        args["year"] = year

    # Tür/puan/yıl yoksa metni serbest arama sorgusu olarak kullan (ör. yönetmen adı).
    if not args:
        query = _clean_query(text)
        if query:
            args["query"] = query
    return args


def _detect_genre(text: str) -> Optional[str]:
    for key, canonical in _GENRE_SYNONYMS.items():
        if key in text:
            return canonical
    return None


_RATING_KEYWORDS = ("puan", "üst", "üzeri", "fazla", "yüksek", "rating")


def _detect_rating(text: str) -> Optional[float]:
    """0-10 arası bir puanı yakalar.

    Yanlış pozitifleri (ör. "Uzaylı Kediler 7" başlığındaki 7) önlemek için
    bir sayı yalnızca ONDALIKLIYSA (8.7) ya da metinde puan bağlamı
    ("puan", "üst", "üzeri"...) varsa puan sayılır.
    """
    has_keyword = any(k in text for k in _RATING_KEYWORDS)
    for m in re.findall(r"\b(\d(?:[.,]\d)?)\b", text):
        has_decimal = "." in m or "," in m
        val = float(m.replace(",", "."))
        if 0 <= val <= 10 and (has_decimal or has_keyword):
            return val
    return None


def _detect_year(text: str) -> Optional[int]:
    m = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    return int(m.group(1)) if m else None


def _extract_title(text: str) -> str:
    """"...ekle" isteğinden film başlığını ayıklar (önce tırnak içi metin)."""
    quoted = re.search(r"['\"‘’“”]([^'\"‘’“”]+)['\"‘’“”]", text)
    if quoted:
        return quoted.group(1).strip()
    return _clean_query(text)


def _clean_query(text: str) -> str:
    """Dolgu kelimeleri atarak sade bir arama sorgusu üretir."""
    words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", text)
    kept = [w for w in words if w.lower() not in _STOPWORDS and not w.isdigit()]
    return " ".join(kept).strip()


def _last_user_message(messages: list[dict[str, Any]]) -> Optional[str]:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return None


def _tool_steps_since_user(messages: list[dict[str, Any]]) -> list[tuple[str, dict]]:
    """Son kullanıcı mesajından sonra çalışmış (tool_adı, sonuç) çiftleri."""
    # Son kullanıcı mesajının indeksini bul.
    last_idx = -1
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            last_idx = i
    steps: list[tuple[str, dict]] = []
    for msg in messages[last_idx + 1 :]:
        if msg.get("role") == "tool":
            try:
                result = json.loads(msg.get("content", "{}"))
            except json.JSONDecodeError:
                result = {}
            steps.append((msg.get("name", ""), result))
    return steps


# --------------------------------------------------------------------------- #
# OpenAI-uyumlu yanıt nesnesi kurucular
# --------------------------------------------------------------------------- #
def _tool(name: str, arguments: dict[str, Any], call_index: int) -> dict[str, Any]:
    return {"type": "tool", "name": name, "arguments": arguments, "call_index": call_index}


def _final(text: str) -> dict[str, Any]:
    return {"type": "final", "content": text}


def _tool_response(name: str, arguments: dict[str, Any], call_index: int):
    """tool_calls içeren bir asistan mesajı taklidi döndürür."""
    tool_call = SimpleNamespace(
        id=f"call_{call_index}",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments, ensure_ascii=False)),
    )
    message = SimpleNamespace(content="", tool_calls=[tool_call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _text_response(content: str):
    """Düz metin (final) asistan mesajı taklidi döndürür."""
    message = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])
