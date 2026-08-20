"""
Yapılandırma — yerel LLM asistanı.

Tüm ayarlar tek yerde. Ortam değişkeniyle override edilebilir, böylece
farklı bir makinede (ör. Ollama kullanan biri) tek satır değiştirmeden çalışır.
"""

import os

# ---------------------------------------------------------------------------
# Yerel model sunucusu
# ---------------------------------------------------------------------------
# LM Studio:  http://localhost:1234/v1   (Developer > Start Server)
# Ollama:     http://localhost:11434/v1  (ollama serve)
BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:1234/v1")

# Yerel sunucular anahtar doğrulaması yapmaz ama OpenAI istemcisi boş kabul etmez.
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "lm-studio")

# LM Studio'da yüklü model kimliği. `lms ps` ile görülebilir.
MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen3-8b")

# ---------------------------------------------------------------------------
# Üretim parametreleri
# ---------------------------------------------------------------------------
# Araç çağıran bir asistanda düşük sıcaklık şart: model argüman uydurmasın.
TEMPERATURE = float(os.getenv("LOCAL_LLM_TEMPERATURE", "0.3"))
# Thinking açıkken düşünme bloğu tek başına 1000+ token yiyebiliyor; cevaba yer
# kalması için yüksek tutuldu.
MAX_TOKENS = int(os.getenv("LOCAL_LLM_MAX_TOKENS", "4096"))

# Qwen3 "thinking" modu. Ölçüm sonucu (bkz. README > Öğrenilenler):
#   Kapalı → hızlı ve ucuz, ama çok adımlı sorularda araca eksik argüman veriyor
#            (500 dolar sorusunda amount'u hiç göndermedi, sonuç yanlış çıktı).
#   Açık   → argümanlar doğru, zincirleme çalışıyor; karşılığında token maliyeti.
# Zincirleme doğruluğu hızdan önemli olduğu için varsayılan açık.
# Kapatmak için: ENABLE_THINKING=0
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "1") == "1"

# Tek bir kullanıcı sorusu için izin verilen ardışık araç turu sayısı.
# Modelin sonsuz döngüye girmesini engeller.
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "6"))

# Bağlamı şişirmemek için tutulan son mesaj sayısı (system hariç).
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "24"))

# ---------------------------------------------------------------------------
# Araç ayarları
# ---------------------------------------------------------------------------
SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "5"))
SEARCH_REGION = os.getenv("SEARCH_REGION", "tr-tr")

# fetch_url ile çekilen sayfadan asistana verilecek azami karakter.
FETCH_MAX_CHARS = int(os.getenv("FETCH_MAX_CHARS", "4000"))

# run_python için saniye cinsinden zaman aşımı.
PYTHON_TIMEOUT = int(os.getenv("PYTHON_TIMEOUT", "10"))

# Kalıcı not veritabanı (asistanın kişisel hafızası).
MEMORY_DB = os.getenv("MEMORY_DB", os.path.join(os.path.dirname(__file__), "memory.db"))

# Varsayılan konum — kullanıcı şehir belirtmezse hava durumu bunu kullanır.
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "İstanbul")

# HTTP istekleri için zaman aşımı.
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "15"))
