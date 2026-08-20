import os
from dotenv import load_dotenv

load_dotenv()

GEREKLI_ANAHTARLAR = [
    "GEMINI_API_KEY",     # sohbet modeli (Google Gemini, OpenAI-uyumlu API)
    "ONET_API_KEY",       # meslek tanimi / gorevler / egitim / buyume (O*NET)
    "ADZUNA_APP_ID",      # Avrupa is ilani talebi ve maasi (Adzuna)
    "ADZUNA_APP_KEY",
]

def eksik_anahtarlar():
    return [a for a in GEREKLI_ANAHTARLAR if not os.getenv(a)]

def kontrol_et():
    eksik = eksik_anahtarlar()
    if eksik:
        print(
            "UYARI: su ortam degiskenleri eksik -> " + ", ".join(eksik)
            + "\nYerelde .env dosyani, HuggingFace Space'te Secrets bolumunu kontrol et. "
            "Eksik anahtara bagli ozellikler calismaz."
        )
    return eksik
