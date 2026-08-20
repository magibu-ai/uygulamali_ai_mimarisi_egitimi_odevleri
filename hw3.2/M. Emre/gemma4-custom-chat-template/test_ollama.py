"""chat_template.jinja'nın GERÇEK modelde çalıştığını doğrular.

Şablonun ürettiği ham metin, Ollama'ya raw=True ile gönderilir. Böylece
Ollama'nın kendi şablonu devre dışı kalır ve modele giden her karakteri
bu proje belirlemiş olur.

Gereksinim:  ollama serve  +  ollama pull gemma4
Çalıştırma:  python test_ollama.py
"""

import json
import urllib.request

from test_render import TOOLS, render

OLLAMA = "http://localhost:11434/api/generate"
MODEL = "gemma4"


def uret(prompt, num_predict=200):
    istek = {
        "model": MODEL,
        "prompt": prompt,
        "raw": True,  # Ollama'nın şablonunu bypass et
        "stream": False,
        "options": {"temperature": 0, "num_predict": num_predict, "stop": ["<turn|>"]},
    }
    veri = json.dumps(istek).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(OLLAMA, data=veri)) as yanit:
        return json.loads(yanit.read())["response"]


def senaryo(baslik, messages, tools=TOOLS):
    prompt = render(messages, tools)
    print("\n" + "=" * 70)
    print(baslik)
    print("=" * 70)
    print("--- MODELE GİDEN SON SATIRLAR ---")
    print(prompt[-260:])
    print("\n--- MODELİN ÜRETTİĞİ ---")
    cikti = uret(prompt)
    print(repr(cikti))
    return cikti


if __name__ == "__main__":
    # 1) Model doğru aracı çağırmalı
    c1 = senaryo(
        "TEST A — araç çağırması bekleniyor",
        [
            {
                "role": "system",
                "content": "Sen bir biyoloji çalışma koçusun. Bilgi sorularını YALNIZCA terim_ara aracıyla yanıtla; aracı çağırmadan tanım yazma.",
            },
            {"role": "user", "content": "Mayoz nedir?"},
        ],
    )

    # 2) Araç sonucu verildiğinde, model o veriye dayanarak cevaplamalı
    c2 = senaryo(
        "TEST B — araç sonucundan cevap üretmesi bekleniyor",
        [
            {
                "role": "system",
                "content": "Sen bir biyoloji çalışma koçusun. Yanıtlarını YALNIZCA araçtan dönen veriye dayandır ve kaynak sayfasını belirt.",
            },
            {"role": "user", "content": "Mayoz nedir?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"function": {"name": "terim_ara", "arguments": {"terim": "mayoz"}}}
                ],
            },
            {
                "role": "tool",
                "name": "terim_ara",
                "content": {
                    "tanim": "Üreme hücrelerinin oluşumunda kromozom sayısının yarıya indiği bölünme.",
                    "kitap_sayfasi": 87,
                    "bulundu": True,
                },
            },
        ],
    )

    # 3) HALÜSİNASYON TESTİ — veritabanında olmayan terim
    c3 = senaryo(
        "TEST C — halüsinasyon engeli (araç boş döndü)",
        [
            {
                "role": "system",
                "content": "Sen bir biyoloji çalışma koçusun. Yanıtlarını YALNIZCA araçtan dönen veriye dayandır. Araç bulundu:false döndürdüyse terimin kaynağında olmadığını söyle ve tanım UYDURMA.",
            },
            {"role": "user", "content": "Kuantum fotosentezi nedir?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "terim_ara",
                            "arguments": {"terim": "kuantum fotosentezi"},
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "name": "terim_ara",
                "content": {"bulundu": False, "sonuc": []},
            },
        ],
    )

    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    print("A) tool_call üretti mi :", "<|tool_call>" in c1 or "call:" in c1)
    print("B) sayfa 87'ye atıf    :", "87" in c2)
    print("C) uydurmayı reddetti  :", any(k in c3.lower() for k in ["bulunma", "yok", "kaynağ", "mevcut değil"]))
