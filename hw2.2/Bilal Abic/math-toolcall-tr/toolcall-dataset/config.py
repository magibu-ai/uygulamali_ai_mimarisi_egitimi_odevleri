"""Ortam degiskenleri ve genel ayarlar."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# --- Saglayicilar -----------------------------------------------------------
# Gemini, OpenAI uyumlu endpoint uzerinden cagrilir; boylece tek bir istemci
# kodu iki saglayiciyi da kullanir.
PROVIDERS = {
    "openai": {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL") or None,
        "model": os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
    },
    "gemini": {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "base_url": os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        ),
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
    },
}

# --- Uretim ayarlari --------------------------------------------------------
LANG = os.getenv("DATASET_LANG", "tr")
# Varsayilan uretici: openai | gemini | both  (--provider ile gecici olarak ezilebilir)
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openai")
TEMPERATURE = float(os.getenv("TEMPERATURE", "1.0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "16000"))
# Reasoning destekleyen modellerde dusunme butcesi: minimal | low | medium | high
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "medium")
WORKERS = int(os.getenv("WORKERS", "4"))
BATCH_SIZE = int(os.getenv("QUESTION_BATCH_SIZE", "5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Goreli yol verilirse proje klasorune gore cozulur (calisma dizininden bagimsiz).
DATA_DIR = Path(os.getenv("DATA_DIR") or "data")
if not DATA_DIR.is_absolute():
    DATA_DIR = ROOT / DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)


def enabled_providers() -> list[str]:
    """API anahtari tanimli olan saglayicilar."""
    return [name for name, cfg in PROVIDERS.items() if cfg["api_key"]]
