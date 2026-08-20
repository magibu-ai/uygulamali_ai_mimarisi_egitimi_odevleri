import json
import os
import re

import gradio as gr
from huggingface_hub import InferenceClient

from bookstore import create_order, get_order_status, search_books

try:
    import spaces
except ImportError:
    class spaces:
        GPU = staticmethod(lambda function: function)

MODEL = os.getenv("HF_MODEL", "Qwen/Qwen3-32B")
PROVIDER = os.getenv("HF_PROVIDER", "auto")
SYSTEM_PROMPT = """Sen Türkçe bir kitapçı asistanısın.
Kitap, fiyat, stok ve sipariş bilgilerini ASLA tahmin etme; yalnızca tool sonuçlarını kullan.
Bir kitap sorulduğunda önce search_books çağır. Sipariş oluşturmadan önce kitap kimliğini tool sonucundan bul.
Tool hata döndürürse hatayı açıkça söyle. Kullanıcı açıkça onaylamadan sipariş oluşturma.
Yanıtlarını kısa ve Türkçe ver."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": "Başlık veya yazara göre kitapları; gerçek fiyat ve stoklarıyla arar.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Başlık/yazar; tümü için boş metin."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Mevcut bir kitap için sipariş oluşturur ve stoğu atomik olarak düşer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {"type": "integer"},
                    "quantity": {"type": "integer", "minimum": 1},
                },
                "required": ["book_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Sipariş numarasıyla gerçek sipariş durumunu getirir.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
]
FUNCTIONS = {
    "search_books": search_books,
    "create_order": create_order,
    "get_order_status": get_order_status,
}


def call_tool(name, arguments, verified_book_ids=None):
    if name not in FUNCTIONS:
        return {"error": f"Bilinmeyen tool: {name}"}
    try:
        parameters = json.loads(arguments) if isinstance(arguments, str) else arguments
        if name == "create_order" and parameters.get("book_id") not in (verified_book_ids or set()):
            return {"error": "Önce search_books çağırıp book_id değerini doğrula."}
        result = FUNCTIONS[name](**parameters)
        if name == "search_books" and verified_book_ids is not None:
            verified_book_ids.update(book["id"] for book in result["books"])
        return result
    except (json.JSONDecodeError, TypeError) as error:
        return {"error": f"Geçersiz tool parametreleri: {error}"}


def render_trace(trace):
    if not trace:
        return ""
    return "\n\n<details><summary>🛠️ Tool İşlem Geçmişi</summary>\n\n```json\n" + json.dumps(
        trace, ensure_ascii=False, indent=2
    ) + "\n```\n</details>"


@spaces.GPU
def chat(message, history):
    if not os.getenv("HF_TOKEN"):
        return "HF_TOKEN tanımlı değil. README'deki kurulum adımını uygulayın."

    verified_book_ids = {
        int(book_id)
        for item in history
        for book_id in re.findall(r"<!--book_id:(\d+)-->", str(item.get("content", "")))
    }
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(
        {
            "role": item["role"],
            "content": re.sub(r"<details>.*?</details>", "", item["content"], flags=re.S),
        }
        for item in history
        if item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str)
    )
    messages.append({"role": "user", "content": message})
    client = InferenceClient(provider=PROVIDER, api_key=os.environ["HF_TOKEN"])
    trace = []

    for _ in range(4):
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto", max_tokens=500
        )
        assistant = response.choices[0].message
        if not assistant.tool_calls:
            reply = re.sub(r"<think>.*?</think>\s*", "", assistant.content or "", flags=re.S)
            markers = "".join(f"<!--book_id:{book_id}-->" for book_id in sorted(verified_book_ids))
            return (reply or "Yanıt üretilemedi.") + render_trace(trace) + markers

        tool_calls = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in assistant.tool_calls
        ]
        messages.append({"role": "assistant", "content": assistant.content or "", "tool_calls": tool_calls})
        for call in assistant.tool_calls:
            result = call_tool(call.function.name, call.function.arguments, verified_book_ids)
            trace.append({"tool": call.function.name, "arguments": call.function.arguments, "result": result})
            print(json.dumps({"tool": call.function.name, "arguments": call.function.arguments, "result": result}, ensure_ascii=False))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    return "En fazla dört tool çağrısına izin veriliyor. Lütfen isteği sadeleştirin."


demo = gr.ChatInterface(
    fn=chat,
    title="📚 Türkçe Kitapçı Asistanı",
    description="Kitap ara, stok ve fiyat öğren, sipariş oluştur veya sipariş durumunu sorgula.",
    examples=["Hangi kitaplar var?", "Oğuz Atay kitabı stokta mı?"],
)

if __name__ == "__main__":
    demo.launch()
