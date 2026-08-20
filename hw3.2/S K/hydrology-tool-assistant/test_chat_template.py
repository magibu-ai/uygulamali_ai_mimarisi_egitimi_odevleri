from pathlib import Path

from transformers import AutoTokenizer

from tool_schemas import TOOLS


MODEL_ID = "srhskrkc/odysseia-bpe-tokenizer"

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "chat_template.jinja"


# Hazır modelin tokenizer'ını yükleme
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

# Yazılan Jinja2 şablonunu tokenizer'a atama
tokenizer.chat_template = TEMPLATE_PATH.read_text(
    encoding="utf-8"
)


messages = [
    {
        "role": "system",
        "content": (
            "Sen bir hidroloji asistanısın. "
            "Veritabanında olmayan bilgileri uydurma."
        ),
    },
    {
        "role": "user",
        "content": (
            "Kirazdere istasyonunun en güncel "
            "debisini kontrol et."
        ),
    },
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_001",
                "type": "function",
                "function": {
                    "name": "get_latest_measurement",
                    "arguments": {
                        "station_name": "Kirazdere"
                    },
                },
            }
        ],
    },
    {
        "role": "tool",
        "content": (
            '{"found": true, '
            '"station": "Kirazdere", '
            '"flow_m3s": 61.2, '
            '"water_level_m": 2.25}'
        ),
    },
]


rendered = tokenizer.apply_chat_template(
    messages,
    tools=TOOLS,
    tokenize=False,
    add_generation_prompt=True,
)


print("=== CUSTOM CHAT TEMPLATE TEST ===")
print()
print(rendered)