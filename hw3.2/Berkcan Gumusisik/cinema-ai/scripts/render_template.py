"""chat_template.jinja'yı örnek bir sohbetle render eden gösterim scripti.

Örnek sohbet, tüm rolleri ve tool-calling akışını kapsar:
  system -> user -> assistant(tool_call) -> tool(response) -> assistant(final)

Çalıştırma:
    python scripts/render_template.py
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_FILE = "chat_template.jinja"

# Modele sunulacak örnek araç tanımı.
EXAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_movies",
            "description": "Film kataloğunda tür/puan/yıla göre arama yapar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "genre": {"type": "string", "description": "Film türü"},
                    "min_rating": {"type": "number", "description": "Minimum puan"},
                },
            },
        },
    }
]

# Tüm rolleri ve tool-call akışını kapsayan örnek konuşma.
EXAMPLE_MESSAGES = [
    {"role": "system", "content": "Sen Cinema-AI'sın, bir film öneri asistanısın."},
    {"role": "user", "content": "Bana puanı 8.5 üstü bir bilim kurgu filmi öner."},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "search_movies",
                    "arguments": {"genre": "Bilim Kurgu", "min_rating": 8.5},
                },
            }
        ],
    },
    {
        "role": "tool",
        "name": "search_movies",
        "content": json.dumps(
            {
                "count": 1,
                "movies": [
                    {
                        "id": 4,
                        "title": "Başlangıç",
                        "year": 2010,
                        "rating": 8.8,
                        "director": "Christopher Nolan",
                    }
                ],
            },
            ensure_ascii=False,
        ),
    },
    {
        "role": "assistant",
        "content": "Sana 'Başlangıç' (2010, 8.8) filmini öneririm — Christopher Nolan imzalı bir bilim kurgu.",
    },
]


def render() -> str:
    """Template'i örnek verilerle render edip metni döndürür."""
    env = Environment(
        loader=FileSystemLoader(str(BASE_DIR)),
        keep_trailing_newline=True,
    )
    # Türkçe karakterlerin \uXXXX'e kaçmaması için (HF ortamının varsayılanıyla aynı).
    env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
    template = env.get_template(TEMPLATE_FILE)
    return template.render(
        messages=EXAMPLE_MESSAGES,
        tools=EXAMPLE_TOOLS,
        add_generation_prompt=True,
    )


if __name__ == "__main__":
    print("=" * 70)
    print("  Cinema-AI — chat_template.jinja render çıktısı")
    print("=" * 70)
    print(render())
    print("=" * 70)
