"""Every setting the assistant reads, plus the redaction helper that keeps keys out of logs.

Values come from .env when present and fall back to the defaults below, so the project
runs with an empty .env — only web search needs a key.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# --- Ollama ------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3:4b-instruct")

# Ollama defaults to a 4096-token window. The system prompt plus eight tool schemas
# plus a couple of tool results overrun that, and the overrun is silent — the oldest
# tokens simply fall out, taking the tool definitions with them. So we set it here.
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))

# Low but not zero: tool arguments should be reproducible, prose should not be stilted.
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))

# Keep the weights resident between turns; reloading 2.5 GB costs ~10 s on this class of GPU.
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "10m")

# Safety brake on the tool loop, in case the model calls tools forever.
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "6"))

# --- Timeouts ----------------------------------------------------------------
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))       # ordinary web APIs
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "45"))         # market data can be slow to gather
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "600"))  # generous: 4 GB of VRAM is not fast

# --- Secrets -----------------------------------------------------------------
TAVILY_KEY = (os.getenv("TAVILY_KEY") or os.getenv("TAVILY_API_KEY") or "").strip()

# --- Borsa MCP ---------------------------------------------------------------
BORSA_MCP_URL = os.getenv("BORSA_MCP_URL", "https://borsa.surucu.dev/mcp")

# The hosted server sleeps when idle and answers 503 for a few seconds while it wakes.
# Measured cold, that is up to half a minute; measured warm, 20 calls in a row all
# succeeded in about 1.5 s each. So: shake hands in the background at start-up, and
# remember answers briefly. Set MCP_WARMUP=false to make the assistant contact the
# market server only when you actually ask it something.
MCP_WARMUP = _env_bool("MCP_WARMUP", True)
MCP_CACHE_TTL = int(os.getenv("MCP_CACHE_TTL", "60"))  # seconds a quote stays fresh

# --- Local data --------------------------------------------------------------
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
DB_PATH = DATA_DIR / "portfolio.db"

# --- Tool limits -------------------------------------------------------------
# Ceiling on how much of a tool's output goes back into the context. A year of daily
# OHLCV bars is tens of thousands of characters and would evict the conversation.
MAX_TOOL_CHARS = int(os.getenv("MAX_TOOL_CHARS", "2600"))

CONFIRM_PYTHON = _env_bool("CONFIRM_PYTHON", True)  # ask before running generated code
PYTHON_TIMEOUT = int(os.getenv("PYTHON_TIMEOUT", "15"))   # wall-clock seconds
PYTHON_MEM_MB = int(os.getenv("PYTHON_MEM_MB", "512"))    # address-space ceiling
PYTHON_MAX_OUTPUT = 4000  # characters of stdout kept


# --- Redaction ---------------------------------------------------------------
# Anything env-shaped and secret-looking, so a key can never reach a log file or the
# terminal even if some future tool echoes its own request back at us.
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD")
_SECRET_VALUES = {
    value
    for name, value in os.environ.items()
    if any(hint in name.upper() for hint in _SECRET_HINTS) and len(value.strip()) >= 8
}
_SECRET_PATTERN = re.compile(r"\btvly-[A-Za-z0-9_-]{8,}\b")


def redact(text: str) -> str:
    """Replace known secret values, and Tavily-shaped keys, with a placeholder."""
    if not text:
        return text
    for value in _SECRET_VALUES:
        text = text.replace(value.strip(), "[REDACTED]")
    return _SECRET_PATTERN.sub("[REDACTED]", text)
