import requests


# =========================================================
# OLLAMA AYARLARI
# =========================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3.5:9b"


# =========================================================
# OLLAMA CHAT İSTEĞİ
# =========================================================

def ollama_chat(messages, tools=None):
    """
    Ollama üzerinde çalışan yerel modele mesaj gönderir.

    Args:
        messages (list):
            Modele gönderilecek konuşma geçmişi.

        tools (list | None):
            Modelin kullanabileceği tool şemaları.

    Returns:
        dict:
            Ollama API tarafından döndürülen cevap.
    """

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        # qwen3.5 "thinking" modeli; kapatılmazsa model çıktı
        # bütçesinin tamamını iç muhakemeye (thinking alanına)
        # harcayıp asıl "content" alanını boş bırakabiliyor. Bu da
        # agent döngüsünde "boş cevap" olarak sayılıp görevin
        # tamamlanamadan bitmesine yol açıyordu.
        "think": False,
    }

    # Tool verilmişse isteğe ekle
    if tools:
        payload["tools"] = tools

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=300,
        )

        # Ollama hata döndürürse gerçek hata mesajını göster
        if not response.ok:

            try:
                hata_detayi = response.json()
            except Exception:
                hata_detayi = response.text

            return {
                "hata": True,
                "mesaj": (
                    f"Ollama HTTP {response.status_code} hatası: "
                    f"{hata_detayi}"
                ),
            }

        return response.json()
    except requests.exceptions.ConnectionError:
        return {
            "hata": True,
            "mesaj": (
                "Ollama sunucusuna bağlanılamadı. "
                "Ollama'nın çalıştığından emin olun."
            ),
        }

    except requests.exceptions.Timeout:
        return {
            "hata": True,
            "mesaj": (
                "Model yanıt verirken zaman aşımı oluştu."
            ),
        }

    except requests.exceptions.RequestException as hata:
        return {
            "hata": True,
            "mesaj": (
                f"Ollama isteği sırasında hata oluştu: {str(hata)}"
            ),
        }

    except Exception as hata:
        return {
            "hata": True,
            "mesaj": (
                f"Beklenmeyen bir hata oluştu: {str(hata)}"
            ),
        }


# =========================================================
# BASİT TEST
# =========================================================

if __name__ == "__main__":

    mesajlar = [
        {
            "role": "user",
            "content": "Merhaba, kendini kısaca tanıt."
        }
    ]

    sonuc = ollama_chat(mesajlar)

    if sonuc.get("hata"):
        print(sonuc["mesaj"])

    else:
        print(sonuc["message"]["content"])