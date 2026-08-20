import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_PATH,
    override=True,
)

HF_TOKEN = os.getenv(
    "HF_TOKEN", 
    "******"
    ).strip()

HF_MODEL = os.getenv(
    "HF_MODEL",
    "Qwen/Qwen2.5-7B-Instruct",
).strip()

HF_PROVIDER = os.getenv(
    "HF_PROVIDER",
    "together",
).strip()

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "",
).strip()

PYPI_API = "https://pypi.org/pypi"
GITHUB_API = "https://api.github.com"
STACKEXCHANGE_API = "https://api.stackexchange.com/2.3"