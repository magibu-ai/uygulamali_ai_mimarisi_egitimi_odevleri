import gradio as gr
import spaces
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import requests
import json
import re
from datetime import datetime, timedelta

# ==========================================
# 1. API Fonksiyonları (Tools)
# ==========================================
def get_earthquakes(start_date: str, end_date: str, min_magnitude: float):
    """
    Belirli tarihler arasında ve minimum büyüklükte olan depremleri getirir.
    """
    try:
        url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_date}&endtime={end_date}&minmagnitude={min_magnitude}"
        res = requests.get(url, timeout=10)
        data = res.json()
        count = data.get('metadata', {}).get('count', 0)
        features = data.get('features', [])[:5] # limit to 5 to avoid huge responses
        results = []
        for f in features:
            props = f.get('properties', {})
            results.append({
                "place": props.get('place'),
                "magnitude": props.get('mag'),
                "time": props.get('time')
            })
        return {"count": count, "top_earthquakes": results}
    except Exception as e:
        return {"error": str(e)}

def get_wildfires(limit: int = 5):
    """
    Dünya genelindeki son aktif orman yangınlarını (NASA EONET üzerinden) getirir.
    """
    try:
        url = "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open"
        res = requests.get(url, timeout=10)
        data = res.json()
        events = data.get('events', [])[:limit]
        results = []
        for e in events:
            geom = e.get('geometry', [{}])[0]
            results.append({
                "title": e.get('title'),
                "date": geom.get('date'),
                "coordinates": geom.get('coordinates')
            })
        return {"count": len(results), "wildfires": results}
    except Exception as e:
        return {"error": str(e)}

available_functions = {
    "get_earthquakes": get_earthquakes,
    "get_wildfires": get_wildfires
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_earthquakes",
            "description": "Belirli tarihler arasında meydana gelen depremleri getirir (USGS API).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Başlangıç tarihi (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "Bitiş tarihi (YYYY-MM-DD)"},
                    "min_magnitude": {"type": "number", "description": "Minimum deprem büyüklüğü (örn: 5.0)"}
                },
                "required": ["start_date", "end_date", "min_magnitude"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_wildfires",
            "description": "Güncel aktif orman yangınlarını NASA EONET üzerinden getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Getirilecek maksimum yangın sayısı"}
                },
                "required": ["limit"]
            }
        }
    }
]

# ==========================================
# 2. Model Yükleme (ZeroGPU Uyumluluğu)
# ==========================================
model_id = "Qwen/Qwen2.5-7B-Instruct"

print(f"Model yükleniyor: {model_id}...")
try:
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )
    print("Model başarıyla yüklendi!")
except Exception as e:
    print(f"Model yüklenirken hata oluştu: {e}")
    model = None
    tokenizer = None

# ==========================================
# 3. Agentic Loop & Tool Execution
# ==========================================
@spaces.GPU(duration=60)
def generate_step(messages):
    """
    Modeli bir adım çalıştırır ve üretilen metni döndürür.
    ZeroGPU ortamında GPU'yu kullanarak çalışır.
    """
    text = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    outputs = model.generate(**inputs, max_new_tokens=1024, temperature=0.3)
    response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=False)

    # Qwen2.5 tool call formatında bitiş token'larını temizleme
    response_text = response_text.replace("<|im_end|>", "")
    return response_text

def parse_tool_calls(text):
    """
    Qwen2.5 formatındaki tool call etiketlerini parse eder.
    <tool_call>
    {"name": "...", "arguments": {...}}
    </tool_call>
    """
    pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
    matches = re.findall(pattern, text, re.DOTALL)
    calls = []
    for match in matches:
        try:
            calls.append(json.loads(match))
        except Exception as e:
            print(f"Tool parse hatası: {e} - Veri: {match}")
    return calls

def chat_interface(user_input, history):
    if not model:
        yield "Model yüklenemediği için yanıt verilemiyor."
        return

    # Sistem mesajı ve geçmişi hazırlama
    messages = [
        {"role": "system", "content": "Sen yetenekli bir afet takip asistanısın. Kullanıcı sorularına cevap verirken gerektiğinde 'get_earthquakes' ve 'get_wildfires' araçlarını kullan. Araçların sonuçlarını inceleyerek doğal dilde cevap ver. Bugünkü tarih: " + datetime.now().strftime("%Y-%m-%d")}
    ]

    for user_msg, asst_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": asst_msg})

    messages.append({"role": "user", "content": user_input})

    final_output = ""
    for _ in range(5):
        try:
            response_text = generate_step(messages)
            messages.append({"role": "assistant", "content": response_text})
        except Exception as e:
            yield final_output + f"\n[Hata]: {str(e)}"
            break

        tool_calls = parse_tool_calls(response_text)
        reasoning_text = re.sub(r"<tool_call>.*?</tool_call>", "", response_text, flags=re.DOTALL).strip()

        if not tool_calls:
            if reasoning_text:
                final_output += f"\n\n{reasoning_text}"
            yield final_output.strip()
            break

        if reasoning_text:
            final_output += f"\n\n🤔 *Düşünce: {reasoning_text}*"

        for call in tool_calls:
            func_name = call.get("name")
            args = call.get("arguments", {})
            
            final_output += f"\n\n🛠️ **Araç Kullanılıyor:** `{func_name}` \n📥 **Girdi:** `{args}`"
            
            if func_name in available_functions:
                try:
                    result = available_functions[func_name](**args)
                    res_json = json.dumps(result, ensure_ascii=False)
                    final_output += f"\n✅ **Çıktı:** `{res_json[:300]}...`"
                    messages.append({"role": "tool", "name": func_name, "content": res_json})
                except Exception as e:
                    error_msg = {"error": str(e)}
                    final_output += f"\n⚠️ **Hata:** `{str(e)}`"
                    messages.append({"role": "tool", "name": func_name, "content": json.dumps(error_msg, ensure_ascii=False)})
            else:
                error_msg = {"error": f"Bilinmeyen fonksiyon: {func_name}"}
                final_output += f"\n⚠️ **Hata:** Bilinmeyen araç"
                messages.append({"role": "tool", "name": func_name, "content": json.dumps(error_msg, ensure_ascii=False)})

        yield final_output + "\n\n*(Araç sonuçları işleniyor...)*"

# ==========================================
# 4. Gradio UI
# ==========================================
with gr.Blocks() as demo:
    gr.Markdown("# 🌍 Afet Takip Asistanı")
    
    chatbot = gr.Chatbot(height=500)
    msg = gr.Textbox(label="Mesajınız", placeholder="Örn: Aktif yangınları listele")
    
    gr.Examples(
        examples=[
            "2026-07-25 ile 2026-07-30 tarihleri arasındaki 5.5 üzeri depremleri listele.",
            "Şu anki aktif büyük orman yangınları hangileri? 3 tanesini getir.",
            "Son 7 günde (2026-07-23 ile 2026-07-30) 6.0'dan büyük deprem oldu mu? Ayrıca şu an aktif orman yangını var mı?"
        ],
        inputs=msg
    )

    def respond(user_message, chat_history):
        if not user_message.strip():
            return chat_history, ""
        chat_history.append((user_message, ""))
        for bot_message in chat_interface(user_message, chat_history[:-1]):
            chat_history[-1] = (user_message, bot_message)
            yield chat_history, ""

    msg.submit(respond, [msg, chatbot], [chatbot, msg], api_name=False)

if __name__ == "__main__":
    demo.launch()