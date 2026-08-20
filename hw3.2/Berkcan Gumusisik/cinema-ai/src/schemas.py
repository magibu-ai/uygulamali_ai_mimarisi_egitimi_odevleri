"""Tool JSON şemaları ve fonksiyon registry'si.

- TOOL_SCHEMAS : OpenAI/Groq "tools" formatında şemalar; modele bu tanımlar
  verilir ve model hangi fonksiyonu hangi argümanlarla çağıracağına karar verir.
- TOOL_REGISTRY: model tarafından üretilen fonksiyon adını gerçek Python
  callable'ına eşler. agent.py bu registry üzerinden çağrıyı yönlendirir.
"""

from __future__ import annotations

from typing import Any, Callable

from . import tools

# Modele sunulan tool tanımları (fonksiyon adı + parametre şeması + açıklama).
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_movies",
            "description": (
                "Film kataloğunda arama yapar. Kullanıcı bir tür, yönetmen, "
                "isim, yıl veya minimum puana göre film istediğinde kullan. "
                "Sadece veritabanındaki gerçek filmleri döndürür."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Başlık, yönetmen veya konu içinde aranacak serbest metin.",
                    },
                    "genre": {
                        "type": "string",
                        "description": "Tür filtresi, ör. 'Bilim Kurgu', 'Dram', 'Animasyon'.",
                    },
                    "min_rating": {
                        "type": "number",
                        "description": "Minimum puan (0-10 arası).",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Yapım yılı.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_movie_details",
            "description": (
                "Belirli bir filmin tüm detaylarını (yönetmen, yıl, puan, özet) "
                "id ile getirir. Film id'sini search_movies sonuçlarından al."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "Filmin veritabanı id'si.",
                    }
                },
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_watchlist",
            "description": (
                "Bir filmi kullanıcının izleme listesine ekler. movie_id "
                "mutlaka search_movies veya get_movie_details ile doğrulanmış "
                "gerçek bir id olmalıdır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "İzleme listesine eklenecek filmin id'si.",
                    },
                    "user": {
                        "type": "string",
                        "description": "Kullanıcı kimliği (verilmezse 'guest').",
                    },
                },
                "required": ["movie_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_watchlist",
            "description": "Kullanıcının izleme listesindeki filmleri getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "Kullanıcı kimliği (verilmezse 'guest').",
                    }
                },
                "required": [],
            },
        },
    },
]

# Fonksiyon adı -> gerçek Python callable eşlemesi.
TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "search_movies": tools.search_movies,
    "get_movie_details": tools.get_movie_details,
    "add_to_watchlist": tools.add_to_watchlist,
    "get_watchlist": tools.get_watchlist,
}
