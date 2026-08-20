"""chat_template.jinja render testi.

Şablonu OpenAI biçimindeki bir sohbet üzerinde çalıştırır ve modelin
göreceği ham metni ekrana basar. Model indirmeye gerek yoktur; yalnızca
jinja2 kullanılır.

Çalıştırma:  python test_render.py
"""

from pathlib import Path

from jinja2 import Environment, StrictUndefined

SABLON = Path(__file__).parent / "chat_template.jinja"

# --- Örnek araç şemaları (OpenAI biçiminde) --------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "terim_ara",
            "description": "Biyoloji sözlüğünden bir terimin tanımını, kitap sayfasını ve kaynak adresini getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "terim": {
                        "type": "string",
                        "description": "Aranacak biyoloji terimi",
                    }
                },
                "required": ["terim"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quiz_getir",
            "description": "Soru bankasından çoktan seçmeli soru getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "konu": {"type": "string", "description": "Soru konusu"},
                    "adet": {"type": "integer", "description": "Kaç soru getirileceği"},
                    "zorluk": {
                        "type": "string",
                        "description": "Zorluk seviyesi",
                        "enum": ["kolay", "orta", "zor"],
                    },
                },
                "required": ["konu"],
            },
        },
    },
]

# --- Tam bir tool-calling turu ---------------------------------------------
MESSAGES = [
    {
        "role": "system",
        "content": "Sen bir biyoloji çalışma koçusun. Yanıtlarını YALNIZCA araçlardan dönen veriye dayandır.",
    },
    {"role": "user", "content": "Mayoz nedir?"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "terim_ara", "arguments": {"terim": "mayoz"}},
            }
        ],
    },
    {
        "role": "tool",
        "name": "terim_ara",
        "tool_call_id": "call_1",
        "content": {
            "tanim": "Üreme hücrelerinin oluşumunda kromozom sayısının yarıya indiği bölünme.",
            "kitap_sayfasi": 87,
            "bulundu": True,
        },
    },
    {
        "role": "assistant",
        "content": "Mayoz, üreme hücrelerinin oluşumunda kromozom sayısının yarıya indiği bölünmedir. (Kaynak: ders kitabı s.87)",
    },
    {"role": "user", "content": "Peki kuantum fotosentezi nedir?"},
]


def render(messages, tools=None, add_generation_prompt=True, **ekstra):
    env = Environment(trim_blocks=False, lstrip_blocks=False, undefined=StrictUndefined)
    env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
    sablon = env.from_string(SABLON.read_text(encoding="utf-8"))
    return sablon.render(
        messages=messages,
        tools=tools,
        add_generation_prompt=add_generation_prompt,
        bos_token="<bos>",
        **ekstra,
    )


def bolum(baslik):
    print("\n" + "=" * 70)
    print(baslik)
    print("=" * 70)


if __name__ == "__main__":
    bolum("TEST 1 — system + tools + tool_call + tool_response zinciri")
    print(render(MESSAGES, TOOLS))

    bolum("TEST 2 — system mesajı YOK, sadece tools (varsayılan talimat devreye girmeli)")
    print(render([{"role": "user", "content": "Mitoz nedir?"}], TOOLS))

    bolum("TEST 3 — araç yok, düz sohbet")
    print(
        render(
            [
                {"role": "user", "content": "Merhaba"},
                {"role": "assistant", "content": "Merhaba, hangi konuya çalışalım?"},
                {"role": "user", "content": "Mayoz"},
            ]
        )
    )

    bolum("TEST 4 — argümanlar JSON string olarak geldiğinde")
    print(
        render(
            [
                {"role": "user", "content": "Bana mayozdan 2 soru sor"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "function": {
                                "name": "quiz_getir",
                                "arguments": '{"konu": "mayoz", "adet": 2}',
                            }
                        }
                    ],
                },
            ],
            TOOLS,
            add_generation_prompt=False,
        )
    )
