import sys
import json
import jinja2

# Ensure UTF-8 output encoding for Windows console (to handle ₺ character)
sys.stdout.reconfigure(encoding='utf-8')

# Read Jinja2 template file
with open("custom_chat_template.jinja", "r", encoding="utf-8") as f:
    template_str = f.read()

template = jinja2.Template(template_str)

# Example Tool Definition
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Fetch the current weather conditions for a specified city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. London"}
                },
                "required": ["city"]
            }
        }
    }
]

# Example Conversation History (Includes Tool Call & Tool Response)
messages = [
    {"role": "system", "content": "You are a helpful AI assistant. Be polite and concise."},
    {"role": "user", "content": "What is the weather like in London today?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": "get_current_weather",
                    "arguments": {"city": "London"}
                }
            }
        ]
    },
    {
        "role": "tool",
        "name": "get_current_weather",
        "content": {"temperature": "24°C", "condition": "Sunny"}
    }
]

# Render template (Set add_generation_prompt=True to prompt assistant response generation)
rendered_prompt = template.render(
    messages=messages,
    tools=tools,
    add_generation_prompt=True
)

print("=== RENDERED PROMPT OUTPUT (₺₺₺ Format) ===")
print(rendered_prompt)
