"""Ortam degiskenlerinden uygulama ayarlari."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str
    ollama_model: str
    ollama_base_url: str
    ollama_timeout: float
    timezone: str
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        """Ortam degiskenlerini okuyup tipli uygulama ayarlarini olusturur."""

        return cls(
            database_path=os.getenv("DATABASE_PATH", "data/planner.db"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            ollama_base_url=os.getenv(
                "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
            ),
            ollama_timeout=float(os.getenv("OLLAMA_TIMEOUT", "300")),
            timezone=os.getenv("APP_TIMEZONE", "Europe/Istanbul"),
            host=os.getenv("APP_HOST", "0.0.0.0"),
            port=int(os.getenv("APP_PORT", "7860")),
        )
