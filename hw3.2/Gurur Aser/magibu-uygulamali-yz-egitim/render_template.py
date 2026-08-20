"""Small terminal demo for the independent custom chat-template delivery."""

from __future__ import annotations

try:  # Works both as ``python -m les6.render_template`` and from les6/.
    from .template import render_chat
except ImportError:  # pragma: no cover - exercised by Space's app root.
    from template import render_chat


def main() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Bir şehrin güncel hava durumunu döndürür.",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            },
        }
    ]
    examples = {
        "normal sohbet": [{"role": "user", "content": "Merhaba!"}],
        "tool çağrısı": [
            {"role": "user", "content": "İstanbul hava durumunu göster."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-demo",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city":"İstanbul"}'},
                    }
                ],
            },
        ],
        "tool sonucu": [
            {
                "role": "tool",
                "tool_call_id": "call-demo",
                "name": "get_weather",
                "content": '{"city": "İstanbul", "temperature_c": 24}',
            }
        ],
    }
    for name, messages in examples.items():
        print(f"\n=== {name} ===")
        print(render_chat(messages, tools=tools if name != "normal sohbet" else None, add_generation_prompt=name != "tool sonucu"))


if __name__ == "__main__":
    main()
