import json
import jinja2

def tojson_filter(val, indent=None):
    if indent is not None:
        return json.dumps(val, ensure_ascii=False, indent=indent)
    return json.dumps(val, ensure_ascii=False)

def render_with_jinja(template_path, messages, tools=None, add_generation_prompt=False):
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    env.filters["tojson"] = tojson_filter

    template = env.from_string(template_content)
    return template.render(
        messages=messages,
        tools=tools,
        add_generation_prompt=add_generation_prompt
    )

def render_with_huggingface(template_path, messages, tools=None, add_generation_prompt=False):
    try:
        from transformers import AutoTokenizer
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        tokenizer.chat_template = template_content
        return tokenizer.apply_chat_template(
            messages,
            tools=tools,
            add_generation_prompt=add_generation_prompt,
            tokenize=False
        )
    except Exception as e:
        return f"[HuggingFace Error / Not Available]: {e}"

if __name__ == "__main__":
    template_file = "chat_template.jinja"

    print("=" * 60)
    print(" 1. Standart Sohbet Senaryosu (PPSF v1.0)")
    print("=" * 60)
    messages_1 = [
        {
            "role": "system",
            "content": "Sen uzman bir eczacı yapay zekâsısın."
        },
        {
            "role": "user",
            "content": "Boğazım ağrıyor."
        }
    ]

    print("\n--- [Jinja2 Output] ---")
    print(render_with_jinja(template_file, messages_1, add_generation_prompt=True))

    print("--- [HuggingFace apply_chat_template Output] ---")
    print(render_with_huggingface(template_file, messages_1, add_generation_prompt=True))

    print("=" * 60)
    print(" 2. Tool Calling & Tool Response Senaryosu")
    print("=" * 60)
    messages_2 = [
        {
            "role": "system",
            "content": "Sen uzman bir eczacı yapay zekâsısın."
        },
        {
            "role": "user",
            "content": "Parol ne işe yarar?"
        },
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "function": {
                        "name": "search_drug",
                        "arguments": {"drug": "Parol"}
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": '{"drug": "Parol", "active_ingredient": "Parasetamol", "usage": "Ağrı kesici ve ateş düşürücü"}'
        }
    ]

    tools_2 = [
        {
            "name": "search_drug",
            "description": "Verilen ilaç hakkında detaylı bilgi arar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug": {"type": "string", "description": "İlaç adı"}
                },
                "required": ["drug"]
            }
        }
    ]

    print("\n--- [Jinja2 Output] ---")
    print(render_with_jinja(template_file, messages_2, tools=tools_2, add_generation_prompt=True))

    print("=" * 60)
    print(" 3. PPSF v1.1 Gelecek Uyumlu Metadata (@THOUGHT & @REFERENCE)")
    print("=" * 60)
    messages_3 = [
        {
            "role": "system",
            "content": "Sen uzman bir eczacı yapay zekâsısın."
        },
        {
            "role": "user",
            "content": "Grip için hangi ilacı kullanmalıyım?",
            "metadata": {
                "reference": "[Kılavuz Doc #42]: Parasetamol 500mg hafif ağrı ve ateş durumlarında tercih edilir."
            }
        },
        {
            "role": "assistant",
            "content": "Ateş ve hafif ağrınız varsa doktor veya eczacınıza danışarak Parasetamol içerikli ilaçlar tercih edebilirsiniz.",
            "metadata": {
                "thought": "Kullanıcının semptomları grip kaynaklı ateş ve hafif ağrı belirtilerine uymaktadır. Referans doküman #42 incelenerek Parasetamol tavsiye edildi."
            }
        }
    ]

    print("\n--- [Jinja2 Output] ---")
    print(render_with_jinja(template_file, messages_3, add_generation_prompt=False))


