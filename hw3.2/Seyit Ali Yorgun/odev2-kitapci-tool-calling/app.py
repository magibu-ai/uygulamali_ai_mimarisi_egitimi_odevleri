import json
import os

import gradio as gr
import spaces
from dotenv import load_dotenv
from groq import Groq

import db

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

MODEL = "llama-3.3-70b-versatile"


@spaces.GPU
def _zerogpu_noop():
    """Unused — satisfies the ZeroGPU hardware startup check. This app is CPU-only."""
    return None


_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_books",
            "description": "Kitapçıdaki kitapları listeler. 'query' verilirse başlık veya yazara göre filtreler, verilmezse tüm katalogu döner. Her kitap için stok ve fiyat bilgisi içerir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Başlık veya yazar adında aranacak kelime (opsiyonel)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Belirtilen kitaptan, belirtilen adette sipariş oluşturur ve stoktan düşer. Stok yetersizse hata döner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {"type": "integer", "description": "list_books çağrısından dönen kitap id'si"},
                    "quantity": {"type": "integer", "description": "Sipariş edilecek adet"},
                    "customer_name": {"type": "string", "description": "Müşterinin adı"},
                },
                "required": ["book_id", "quantity", "customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": "Verilen sipariş numarasının (order_id) durumunu, hangi kitap ve ne kadar olduğunu döner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "create_order çağrısından dönen sipariş numarası"},
                },
                "required": ["order_id"],
            },
        },
    },
]

AVAILABLE_FUNCTIONS = {
    "list_books": db.list_books,
    "create_order": db.create_order,
    "check_order_status": db.check_order_status,
}

SYSTEM_PROMPT = (
    "Sen bir kitapçının sipariş asistanısın. Elinde list_books, create_order ve "
    "check_order_status araçları var. KURALLAR: "
    "1) Kitap adı, yazar, fiyat, stok gibi bilgileri ASLA uydurma — her zaman önce list_books "
    "çağır ve sadece dönen gerçek veriyi kullan. "
    "2) Katalogda olmayan bir kitap sorulursa, 'bu kitap katalogda yok' de, var gibi davranma. "
    "3) Sipariş oluşturmadan önce book_id'yi list_books sonucundan al, tahmin etme. "
    "4) Stok yetersizse veya hata dönerse bunu kullanıcıya net şekilde söyle. "
    "5) Kısa, net ve Türkçe yanıt ver."
)


def run_agent(user_message: str, history: list):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    trace_lines = []
    turn_num = 1
    max_turns = 6

    while turn_num <= max_turns:
        for attempt in range(3):
            try:
                response = get_client().chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto",
                )
                break
            except Exception as e:
                if "tool_use_failed" in str(e) and attempt < 2:
                    continue
                raise
        msg = response.choices[0].message

        if not msg.tool_calls:
            final_text = msg.content or ""
            if trace_lines:
                trace = "\n".join(trace_lines)
                return f"```\n{trace}\n```\n\n**Yanıt:**\n{final_text}"
            return final_text

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        trace_lines.append(f"[Tur {turn_num}] Araç Çağrıları:")
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            func = AVAILABLE_FUNCTIONS.get(name)
            result = func(**args) if func else {"error": f"Unknown tool {name}"}

            args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
            trace_lines.append(f"   -> {name}({args_str})")
            trace_lines.append(f"   <- {result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

        turn_num += 1

    return "Üzgünüm, çok fazla araç çağrısı yapıldı, yanıt üretilemedi."


def chat_fn(message, history):
    if not os.environ.get("GROQ_API_KEY"):
        return "GROQ_API_KEY ortam değişkeni ayarlanmamış. Lütfen Space secrets kısmına ekleyin."
    try:
        return run_agent(message, history)
    except Exception as e:
        return f"Hata: {e}"


demo = gr.ChatInterface(
    fn=chat_fn,
    title="📚 Kitapçı Asistanı — Tool Calling Demo",
    description=(
        "Model, katalog/stok/fiyat sorularında `list_books`, sipariş için `create_order`, "
        "sipariş takibi için `check_order_status` araçlarını otomatik çağırır. Tüm veriler "
        "gerçek bir SQLite veritabanından gelir; model katalogda olmayan bir kitabı asla uydurmaz. "
        "Arka planda hangi aracın hangi parametrelerle çağrıldığı yanıtın üstünde gösterilir.\n\n"
        "Örnek: *'Elinizde Orwell'in kitabı var mı, varsa 2 tane sipariş vermek istiyorum, adım Ali.'*"
    ),
    examples=[
        "Katalogda hangi kitaplar var?",
        "1984 kitabından 2 adet sipariş vermek istiyorum, adım Ayşe.",
        "Fahrenheit 451'den 1 tane alabilir miyim?",
        "3 numaralı siparişimin durumu ne?",
    ],
)

if __name__ == "__main__":
    demo.launch()
