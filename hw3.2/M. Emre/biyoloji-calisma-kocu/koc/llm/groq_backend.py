"""Groq backend — HF Space'teki canlı demo bunu kullanır.

Açık kaynak bir model (Llama 3.3 70B) Groq altyapısında çalışır ve OpenAI uyumlu
tool-calling arayüzü sunar. Chat template sunucu tarafında uygulanır; bu yüzden
projenin kendi chat_template.jinja dosyası burada DEVREDE DEĞİLDİR
(bkz. ollama_backend.py).
"""

from __future__ import annotations

import json
import os

from groq import Groq

try:  # yerelde .env dosyasından oku; HF Space'te Secret zaten ortam değişkenidir
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

VARSAYILAN_MODEL = "llama-3.3-70b-versatile"


class GroqBackend:
    ad = "Groq (llama-3.3-70b)"
    kendi_sablonu_kullanir = False

    def __init__(self, model: str = None, api_key: str = None):
        anahtar = api_key or os.environ.get("GROQ_API_KEY")
        if not anahtar:
            raise RuntimeError("GROQ_API_KEY tanımlı değil.")
        self.istemci = Groq(api_key=anahtar)
        self.model = model or os.environ.get("GROQ_MODEL", VARSAYILAN_MODEL)
        self.son_istek = ""
        self.son_ham_yanit = ""

    def son_etkilesim(self) -> dict:
        return {
            "baslik": "API'ye giden mesaj listesi (chat template sunucu tarafında uygulanır)",
            "istek": self.son_istek,
            "yanit": self.son_ham_yanit,
            "dil": "json",
        }

    def sohbet(self, messages: list[dict], tools: list[dict]) -> dict:
        api_mesajlari = _api_bicimine_cevir(messages)
        self.son_istek = json.dumps(api_mesajlari, ensure_ascii=False, indent=2)
        try:
            yanit = self.istemci.chat.completions.create(
                model=self.model,
                messages=api_mesajlari,
                tools=tools,
                tool_choice="auto",
                temperature=0,
                # Bağımlı zincirlerde (quiz_getir -> cevap_kaydet) modelin önceki
                # aracın sonucunu görmeden ikinciyi çağırmasını engeller.
                parallel_tool_calls=False,
            )
        except Exception as hata:
            # Groq araç çağrısını sunucu tarafında şemaya karşı doğrular. Model
            # şema dışı bir çağrı üretirse istek 400 ile döner; arayüzün çökmesi
            # yerine kullanıcıya anlaşılır bir mesaj gösterilir.
            if "tool_use_failed" in str(hata):
                return {
                    "content": "Aracı çağırırken bir biçim hatası oluştu. Sorunu biraz "
                    "daha sade yazar mısın?",
                    "tool_calls": [],
                }
            raise

        mesaj = yanit.choices[0].message
        self.son_ham_yanit = json.dumps(
            {
                "content": mesaj.content,
                "tool_calls": [
                    {"name": c.function.name, "arguments": c.function.arguments}
                    for c in (mesaj.tool_calls or [])
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        return {
            "content": mesaj.content,
            "tool_calls": [
                {
                    "id": c.id,
                    "name": c.function.name,
                    "arguments": _argumanlari_coz(c.function.arguments),
                }
                for c in (mesaj.tool_calls or [])
            ],
        }


def _argumanlari_coz(argumanlar) -> dict:
    if isinstance(argumanlar, dict):
        return argumanlar
    try:
        return json.loads(argumanlar or "{}")
    except json.JSONDecodeError:
        return {}


def _api_bicimine_cevir(messages: list[dict]) -> list[dict]:
    """Ajan geçmişini OpenAI/Groq API'sinin beklediği biçime getirir.

    Ajan, araç sonuçlarını dict olarak tutar (yerel backend'de şablona dict
    vermek gerekir); API ise string bekler.
    """
    cikti = []
    for mesaj in messages:
        yeni = dict(mesaj)
        if not isinstance(yeni.get("content"), (str, type(None))):
            yeni["content"] = json.dumps(yeni["content"], ensure_ascii=False)
        if yeni.get("role") == "assistant" and yeni.get("tool_calls"):
            yeni["tool_calls"] = [
                {
                    "id": c["id"],
                    "type": "function",
                    "function": {
                        "name": c["function"]["name"],
                        "arguments": json.dumps(c["function"]["arguments"], ensure_ascii=False)
                        if isinstance(c["function"]["arguments"], dict)
                        else c["function"]["arguments"],
                    },
                }
                for c in yeni["tool_calls"]
            ]
        cikti.append(yeni)
    return cikti
