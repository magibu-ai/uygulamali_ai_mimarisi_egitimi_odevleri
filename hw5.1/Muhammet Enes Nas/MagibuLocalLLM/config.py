"""Proje genelinde kullanilan yapilandirma.

Model, URL, zaman asimi ve API anahtarlari tek bir yerde tutulur; diger dosyalar
buradan okur. Bir ayari degistirmek istersen ya bu dosyaya ya da '.env' dosyasina
dokunman yeter.

Oncelik sirasi:  ortam degiskeni  >  .env dosyasi  >  buradaki varsayilan
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


# ─────────────────────────────────────────
# .env OKUYUCU
# ─────────────────────────────────────────
# python-dotenv kurmak yerine 10 satirlik bir okuyucu yaziyoruz: bagimlilik
# eklemiyor ve ne yaptigi tamamen gorunur. Zaten .env dosyasi da bu kadar basit.

def _load_dotenv(path: Path) -> None:
    """'.env' dosyasindaki KEY=VALUE satirlarini ortam degiskenlerine yazar.

    Gercek ortam degiskeni zaten tanimliysa DOKUNMAZ — boylece
    'set TAVILY_API_KEY=... && python main.py' dosyayi ezebilir.
    """
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")  # tirnaklari soy
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")


# ─────────────────────────────────────────
# OLLAMA
# ─────────────────────────────────────────

# Ollama sunucu adresi (varsayilan: localhost:11434)
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Sohbet modeli — arac cagirma (tool calling) destekleyen bir model olmali.
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:1.7b")

# Bilgi bankasi aramasinda kullanilacak embedding modeli anahtari.
# Gecerli degerler ollama_client.EMBED_MODELS icinde tanimli.
EMBED_MODEL = os.getenv("EMBED_MODEL", "magibu")

# Ollama'ya verilen sure. 300 sn interaktif sohbet icin cok uzundu: model tekrar
# dongusune girdiginde kullanici 5 dakika bos ekrana bakiyordu. 90 sn, ilk model
# yuklemesi icin yeterli ama takilmayi makul surede yakaliyor.
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "90"))

# Modelin GPU bellekinde kalma suresi. Ollama varsayilani 5 dakikadir; interaktif
# sohbette dusunup soru yazarken bu sure dolar, model bosaltilir ve bir sonraki
# soru yeniden yukleme bekler. Uzatmak "neden bazen cok yavas" sorusunu cozer.
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

# Baglam penceresi. Sistem istemi + arac semalari TEK BASINA ~1500 token tutuyor;
# uzerine sohbet gecmisi ve arac ciktilari (Tavily sonuclari uzundur) binince
# Ollama'nin 4096'lik varsayilani tasar. Tastiginda en eski mesajlar SESSIZCE
# atilir: model sistem istemini unutur, yanlis arac secer. 8192 bu riski kaldirir
# ve 0.6b bir modelde ek VRAM maliyeti onemsizdir.
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

# Model sicakligi. Arac secimi bir siniflandirma isi oldugu icin dusuk tutuyoruz.
# AMA 0.0 KULLANMAYIN: tam greedy cozumleme kucuk modellerde kendini tekrar eden
# sonsuz uretime yol aciyor (olculdu — model dakikalarca ayni cumleyi yaziyordu).
# 0.1 hem kararli hem de dongulerden cikabiliyor.
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))

# Tek bir cevapta uretilebilecek azami token. Tavan olmazsa model tekrar
# dongusune girdiginde baglam dolana kadar (8192 token) uretmeye devam eder.
# Bu asistanin cevaplari kisa; 512 fazlasiyla yeterli, tavan olarak da guvenli.
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))

# Tekrar cezasi — ayni ifadeyi tekrar tekrar uretmeyi zorlastirir.
# num_predict tavani dongunun SURESINI sinirlar, bu ise dongune GIRMESINI zorlastirir.
REPEAT_PENALTY = float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.15"))

# Sohbet dongusunde araclarin ust uste cagrilma siniri (sonsuz dongu korumasi).
MAX_TOOL_ROUNDS = 5


# ─────────────────────────────────────────
# DIS API'LER
# ─────────────────────────────────────────

# Tavily arama API'si. Bos ise web_search otomatik olarak DuckDuckGo'ya duser.
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

# Dis HTTP istekleri icin zaman asimi (saniye).
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))


# ─────────────────────────────────────────
# BILGI BANKASI (RAG)
# ─────────────────────────────────────────

# Vektorler bu klasorde diske yazilir; silmek indeksi sifirlar.
DB_PATH = str(BASE_DIR / "chroma_db")

# Indekslenecek finans bilgi bankasi (JSON).
KB_PATH = str(BASE_DIR / "data" / "finans_bilgi_bankasi.json")
