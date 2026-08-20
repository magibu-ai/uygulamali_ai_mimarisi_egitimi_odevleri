import os
import requests

BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:7b-instruct")


def _post(path, payload):
    try:
        resp = requests.post(f"{BASE_URL}{path}", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Ollama'ya bağlanılamadı. Lütfen 'ollama serve' komutuyla servisi başlatın."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama HTTP hatası: {e}")
    except Exception as e:
        raise RuntimeError(f"Ollama isteği başarısız: {e}")


def chat(messages, model=CHAT_MODEL, tools=None, temperature=0.1):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload)["message"]
