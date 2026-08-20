"""Ortam değişkenlerini tek yerden okuyan yapılandırma modülü.

Kod provider-agnostiktir: OpenAI-uyumlu (base_url + model + api_key) herhangi
bir sağlayıcı ile çalışır. Varsayılan sağlayıcı Groq'tur (ücretsiz tier).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    # .env dosyası varsa otomatik yükle (yoksa sessizce geç).
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv kurulu değilse sorun değil
    pass

# Proje kök dizini (bu dosya src/ altında).
BASE_DIR = Path(__file__).resolve().parent.parent

# SQLite veritabanı yolu ve seed verisi.
DB_PATH = os.getenv("CINEMA_DB_PATH", str(BASE_DIR / "cinema.db"))
SEED_PATH = str(BASE_DIR / "data" / "seed_movies.json")


@dataclass(frozen=True)
class LLMConfig:
    """LLM sağlayıcı ayarları.

    backend değerleri:
        "auto"   : API anahtarı varsa gerçek model, yoksa yerel mock (varsayılan)
        "openai" : her zaman gerçek OpenAI-uyumlu endpoint (anahtar zorunlu)
        "mock"   : her zaman yerel kural tabanlı mock model (API'siz test)
    """

    api_key: str
    base_url: str
    model: str
    backend: str = "auto"

    @property
    def use_mock(self) -> bool:
        """Bu yapılandırma yerel mock modeli mi kullanacak?"""
        if self.backend == "mock":
            return True
        if self.backend == "openai":
            return False
        # "auto": anahtar yoksa mock'a düş.
        return not bool(self.api_key)

    @property
    def is_ready(self) -> bool:
        """Yanıt üretilebilir mi? Mock her zaman hazırdır; gerçek model anahtar ister."""
        return self.use_mock or bool(self.api_key)


def get_llm_config() -> LLMConfig:
    """Ortam değişkenlerinden LLM yapılandırmasını üretir."""
    return LLMConfig(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        backend=os.getenv("LLM_BACKEND", "auto").lower(),
    )
