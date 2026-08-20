# NovaCall - Custom LLM Chat Template with ₺₺₺ Special Tokens

This project provides a custom **Jinja2 chat template** designed for Large Language Models (LLMs). It wraps **System, User, Assistant** roles and **Tool Calling** (Function Calling & Tool Responses) parameters using clean `₺₺₺` special tokens.

---

## 🏷️ Special Token Architecture

| Structure | Opening & Closing Tag |
|---|---|
| **System Message** | `₺₺₺System₺₺₺` ... `₺₺₺System₺₺₺` |
| **User Message** | `₺₺₺User₺₺₺` ... `₺₺₺User₺₺₺` |
| **Assistant Message** | `₺₺₺Assistant₺₺₺` ... `₺₺₺Assistant₺₺₺` |
| **Tools Schema** | `₺₺₺ToolsSchema₺₺₺` ... `₺₺₺ToolsSchema₺₺₺` |
| **Tool Call (Model)** | `₺₺₺ToolCall₺₺₺` ... `₺₺₺ToolCall₺₺₺` |
| **Tool Response (API/System)** | `₺₺₺ToolResponse₺₺₺` ... `₺₺₺ToolResponse₺₺₺` |

---

## 📝 Rendered Output Example

```text
₺₺₺System₺₺₺
You are a helpful AI assistant. Be polite and concise.

You can use the following functions/tools. When you want to call a tool, respond with the appropriate JSON format.
₺₺₺ToolsSchema₺₺₺
[
  {
    "function": {
      "description": "Fetch the current weather conditions for a specified city.",
      "name": "get_current_weather",
      "parameters": {
        "properties": {
          "city": {
            "description": "City name, e.g. London",
            "type": "string"
          }
        },
        "required": [
          "city"
        ],
        "type": "object"
      }
    },
    "type": "function"
  }
]
₺₺₺ToolsSchema₺₺₺
₺₺₺System₺₺₺
₺₺₺User₺₺₺
What is the weather like in London today?
₺₺₺User₺₺₺
₺₺₺Assistant₺₺₺
₺₺₺ToolCall₺₺₺
{"name": "get_current_weather", "arguments": {"city": "London"}}
₺₺₺ToolCall₺₺₺
₺₺₺Assistant₺₺₺
₺₺₺ToolResponse₺₺₺
{"name": "get_current_weather", "content": {"condition": "Sunny", "temperature": "24\u00b0C"}}
₺₺₺ToolResponse₺₺₺
₺₺₺Assistant₺₺₺
```

---

## 📂 Project Structure

- [custom_chat_template.jinja](file:///c:/Users/90535/source/magibu/custom_chat_template/custom_chat_template.jinja): Core Jinja2 template wrapping model roles and tool calling logic.
- [test_template.py](file:///c:/Users/90535/source/magibu/custom_chat_template/test_template.py): Python validation script rendering the template with Jinja2.

---

## 🚀 How to Run

Ensure Jinja2 is installed and run the test script:

```bash
pip install jinja2
python test_template.py
```
