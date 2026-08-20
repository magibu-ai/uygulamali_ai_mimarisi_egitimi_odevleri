"""chat_template.jinja'yı örnek bir konuşma üzerinde render edip çıktıyı gösterir."""
import json
import os

from jinja2 import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    trim_blocks=True,
    lstrip_blocks=True,
)
template = env.get_template("chat_template.jinja")

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Bir şehrin güncel hava durumunu döner.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]

messages = [
    {"role": "system", "content": "Sen yardımsever bir asistansın."},
    {"role": "user", "content": "İstanbul'da hava nasıl?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": "get_weather", "arguments": {"city": "İstanbul"}}}
        ],
    },
    {"role": "tool", "content": json.dumps({"temp_c": 27, "sky": "açık"}, ensure_ascii=False)},
    {"role": "assistant", "content": "İstanbul'da hava açık ve sıcaklık 27°C."},
]

output = template.render(
    messages=messages,
    tools=tools,
    bos_token="<s>",
    add_generation_prompt=False,
)
print(output)
