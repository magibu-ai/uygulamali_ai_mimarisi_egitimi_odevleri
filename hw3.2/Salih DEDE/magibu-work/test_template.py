"""Ozgun chat_template.jinja dosyasini saf Jinja2 ile render edip test eder."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent


def raise_exception(message):
    raise ValueError(message)


def build_env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    env.filters["tojson"] = lambda value: json.dumps(value, ensure_ascii=False)
    env.globals["raise_exception"] = raise_exception
    return env


TOOLS = [
    {
        "name": "search_wikipedia",
        "description": "Verilen konu hakkinda Wikipedia'dan ozet bilgi ve konum getirir.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "check_balance",
        "description": "Kullanicinin THY cuzdan bakiyesini dondurur.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_flights",
        "description": "Verilen sehre, tarihe gore THY ucus secenekleri arar.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["destination", "date"],
        },
    },
]

MESSAGES = [
    {
        "role": "system",
        "content": (
            "Sen bir THY seyahat asistanisin. Sadece tool'lardan donen gercek "
            "verileri kullan, uydurma bilgi verme."
        ),
    },
    {"role": "user", "content": "Eyfel Kulesi'ne gitmek istiyorum, bana gunluk bir plan yapar misin?"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"name": "search_wikipedia", "arguments": {"query": "Eyfel Kulesi"}}],
    },
    {
        "role": "tool",
        "name": "search_wikipedia",
        "content": {"title": "Eyfel Kulesi", "city": "Paris", "country": "Fransa"},
    },
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"name": "check_balance", "arguments": {}}],
    },
    {
        "role": "tool",
        "name": "check_balance",
        "content": {"balance": 12500, "currency": "TRY"},
    },
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "name": "search_flights",
                "arguments": {"destination": "Paris", "date": "2026-09-10"},
            }
        ],
    },
    {
        "role": "tool",
        "name": "search_flights",
        "content": {
            "flights": [
                {"flight_no": "TK1823", "departure": "10:15", "price": 4200, "currency": "TRY"}
            ]
        },
    },
    {
        "role": "assistant",
        "content": (
            "Bakiyen 12.500 TRY, TK1823 sefer sayili 2026-09-10 10:15 Paris ucusu "
            "4.200 TRY. Eyfel Kulesi Paris, Fransa'da; gunu oglen kule ziyareti, "
            "aksam Seine nehri kiyisinda yemekle planlayabilirsin."
        ),
    },
]


def main() -> None:
    env = build_env()
    template = env.get_template("chat_template.jinja")

    print("=== add_generation_prompt=False ===")
    print(template.render(messages=MESSAGES, tools=TOOLS, add_generation_prompt=False))

    print("\n=== add_generation_prompt=True ===")
    print(template.render(messages=MESSAGES, tools=TOOLS, add_generation_prompt=True))


if __name__ == "__main__":
    main()
