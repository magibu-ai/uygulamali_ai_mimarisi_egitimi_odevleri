"""Yerel backend — Ollama üzerinde Gemma 4, projenin KENDİ chat template'i ile.

Groq backend'inden farkı: burada prompt'u sunucu değil bu proje üretir.
messages + tools listesi `koc/chat_template.jinja` ile düz metne çevrilir ve
Ollama'ya `raw=True` gönderilir; böylece Ollama'nın kendi şablonu devre dışı
kalır. Modelin ürettiği Gemma DSL biçimindeki tool-call metni burada parse
edilerek ajanın beklediği sözlüğe dönüştürülür.

Bu dosya, projenin kendi chat template'inin gerçek bir modelde çalıştığının kanıtıdır.
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from jinja2 import Environment

SABLON_YOLU = Path(__file__).resolve().parent.parent / "chat_template.jinja"
VARSAYILAN_ADRES = "http://localhost:11434/api/generate"
VARSAYILAN_MODEL = "gemma4"

# <|tool_call>call:AD{GÖVDE}<tool_call|>
CAGRI_DESENI = re.compile(r"<\|tool_call>call:([A-Za-z_][\w]*)\{(.*?)\}<tool_call\|>", re.S)
METIN_DESENI = re.compile(r'<\|"\|>(.*?)<\|"\|>', re.S)


class OllamaBackend:
    ad = "Yerel Gemma 4 (Ollama, kendi chat_template.jinja)"
    kendi_sablonu_kullanir = True

    def __init__(self, model: str = VARSAYILAN_MODEL, adres: str = VARSAYILAN_ADRES):
        self.model = model
        self.adres = adres
        self.sablon = Environment().from_string(SABLON_YOLU.read_text(encoding="utf-8"))
        self.son_prompt = ""  # şeffaflık paneli için: modele giden ham metin
        self.son_ham_yanit = ""  # modelin ürettiği ham metin (parse edilmeden önce)

    def sohbet(self, messages: list[dict], tools: list[dict]) -> dict:
        self.son_prompt = self.sablon.render(
            messages=messages,
            tools=tools,
            add_generation_prompt=True,
            bos_token="<bos>",
        )
        self.son_ham_yanit = self._uret(self.son_prompt)
        return _yaniti_coz(self.son_ham_yanit)

    def son_etkilesim(self) -> dict:
        return {
            "baslik": "Modele giden ham metin (kendi chat_template.jinja ile üretildi)",
            "istek": self.son_prompt,
            "yanit": self.son_ham_yanit,
            "dil": "text",
        }

    def _uret(self, prompt: str, uzunluk: int = 400) -> str:
        istek = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "raw": True,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": uzunluk,
                    "stop": ["<turn|>"],
                },
            }
        ).encode("utf-8")
        with urllib.request.urlopen(urllib.request.Request(self.adres, data=istek)) as yanit:
            return json.loads(yanit.read())["response"]


# --------------------------------------------------------------------------
# Gemma DSL çözümleme
# --------------------------------------------------------------------------


def _yaniti_coz(ham: str) -> dict:
    cagrilar = []
    for sira, eslesme in enumerate(CAGRI_DESENI.finditer(ham)):
        cagrilar.append(
            {
                "id": f"yerel_{sira}",
                "name": eslesme.group(1),
                "arguments": _argumanlari_coz(eslesme.group(2)),
            }
        )
    metin = CAGRI_DESENI.sub("", ham).strip()
    return {"content": metin or None, "tool_calls": cagrilar}


def _argumanlari_coz(govde: str) -> dict:
    """`terim:<|"|>mayoz<|"|>,adet:2` -> {"terim": "mayoz", "adet": 2}

    String değerler <|"|> token'ları arasındadır ve virgül içerebilir. Bu yüzden
    önce string blokları yer tutucuyla değiştirilir, ayrıştırma ondan sonra yapılır.
    """
    if not govde.strip():
        return {}

    metinler: list[str] = []

    def yer_tutucu(eslesme):
        metinler.append(eslesme.group(1))
        return f"\x00{len(metinler) - 1}\x00"

    guvenli = METIN_DESENI.sub(yer_tutucu, govde)

    argumanlar = {}
    for parca in _ust_seviye_bol(guvenli):
        if ":" not in parca:
            continue
        anahtar, _, deger = parca.partition(":")
        argumanlar[anahtar.strip()] = _degeri_coz(deger.strip(), metinler)
    return argumanlar


def _ust_seviye_bol(metin: str) -> list[str]:
    """Virgülden böler ama köşeli/süslü parantez içindekilere dokunmaz."""
    parcalar, derinlik, son = [], 0, 0
    for i, karakter in enumerate(metin):
        if karakter in "[{":
            derinlik += 1
        elif karakter in "]}":
            derinlik -= 1
        elif karakter == "," and derinlik == 0:
            parcalar.append(metin[son:i])
            son = i + 1
    parcalar.append(metin[son:])
    return [p for p in parcalar if p.strip()]


def _degeri_coz(deger: str, metinler: list[str]):
    if deger.startswith("\x00") and deger.endswith("\x00"):
        return metinler[int(deger.strip("\x00"))]
    if deger in ("true", "false"):
        return deger == "true"
    if deger == "null":
        return None
    if deger.startswith("[") and deger.endswith("]"):
        return [_degeri_coz(p.strip(), metinler) for p in _ust_seviye_bol(deger[1:-1])]
    try:
        return int(deger)
    except ValueError:
        pass
    try:
        return float(deger)
    except ValueError:
        return deger
