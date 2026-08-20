import os
import json
import requests
import urllib3
import gradio as gr
from openai import OpenAI
import spaces

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. OPEN-METEO HAVA DURUMU & DÖNÜŞÜM FONKSİYONLARI
# ==========================================

def get_weather(city: str) -> str:
    """Open-Meteo API'sinden belirtilen şehrin canlı hava durumunu çeker."""
    if isinstance(city, dict):
        city = city.get("city", "")
        
    clean_city = str(city).strip("'\" \t\n\r")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_city}&count=1&language=tr&format=json"
        geo_res = requests.get(geo_url, headers=headers, timeout=5, verify=False)
        
        if geo_res.status_code == 200 and "results" in geo_res.json():
            location = geo_res.json()["results"][0]
            lat = location["latitude"]
            lon = location["longitude"]
            city_official_name = location.get("name", clean_city)
            
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            weather_res = requests.get(weather_url, headers=headers, timeout=5, verify=False)
            
            if weather_res.status_code == 200:
                current = weather_res.json().get("current_weather", {})
                temp_c = current.get("temperature")
                
                info = {
                    "city": city_official_name,
                    "temp_c": temp_c,
                    "unit": "C"
                }
                return json.dumps(info, ensure_ascii=False)
                
        return json.dumps({"error": f"'{clean_city}' şehri için hava durumu verisi bulunamadı."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Hava durumu isteğinde hata: {str(e)}"}, ensure_ascii=False)


def convert_temperature(value: float, to_unit: str = "F") -> str:
    """Sıcaklık değerini Celsius'tan Fahrenheit'a (veya tersine) dönüştürür."""
    try:
        val = float(value)
        unit = str(to_unit).strip().upper()
        
        if any(u in unit for u in ["F", "FAHRENHEIT", "FAHRENAYT"]):
            res_val = round((val * 9 / 5) + 32, 1)
            target_unit = "F"
        elif any(u in unit for u in ["C", "CELSIUS", "SANTİGRAT"]):
            res_val = round((val - 32) * 5 / 9, 1)
            target_unit = "C"
        else:
            res_val = round((val * 9 / 5) + 32, 1)
            target_unit = "F"
            
        return json.dumps({"original_value": val, "converted_value": res_val, "unit": target_unit}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Dönüşüm hatası: {str(e)}"}, ensure_ascii=False)

# ==========================================
# 2. TOOL (FUNCTION) ŞEMALARI
# ==========================================

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Belirtilen şehrin anlık canlı hava sıcaklığını Celsius (C) cinsinden getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Hava durumu öğrenilmek istenen şehir adı (Örn: Tokyo, Erzincan, Ankara, London)"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "convert_temperature",
            "description": "Celsius cinsinden alınan sıcaklık değerini Fahrenheit (F) birimine dönüştürür. Sıcaklık Fahrenheit veya Fahrenayt olarak sorulduğunda bu araç tetiklenmelidir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "Dönüştürülecek Celsius sıcaklık değeri"
                    },
                    "to_unit": {
                        "type": "string",
                        "description": "Dönüştürülecek hedef birim ('F' veya 'C')",
                        "enum": ["F", "C"]
                    }
                },
                "required": ["value", "to_unit"]
            }
        }
    }
]

# ==========================================
# 3. AGENTIC EXECUTION DÖNGÜSÜ
# ==========================================

@spaces.GPU
def run_agent(user_query: str):
    if not user_query.strip():
        return "Lütfen bir soru girin."
    
    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        return "Hata: Space Secrets üzerinde HF_TOKEN tanımlanmamış."

    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=hf_token
    )
    
    system_prompt = (
        "Sen hava durumu asistanısın. Şehir sıcaklıkları için 'get_weather' kullan."
        "Eğer kullanıcı Fahrenheit/Fahrenayt istiyorsa, önce 'get_weather' ile sıcaklığı al,"
        "ardından 'convert_temperature' aracını çalıştırarak Fahrenheit'a çevir."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]
    
    execution_logs = []
    turn_count = 1
    max_turns = 5

    while turn_count <= max_turns:
        try:
            response = client.chat.completions.create(
                model="Qwen/Qwen3.5-9B",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
        except Exception as e:
            return f"Model hatası: {str(e)}"

        msg = response.choices[0].message
        
        if not msg.tool_calls:
            final_text = msg.content
            if not final_text or not final_text.strip():
                try:
                    retry_res = client.chat.completions.create(
                        model="Qwen/Qwen3.5-9B",
                        messages=messages
                    )
                    final_text = retry_res.choices[0].message.content
                except Exception:
                    final_text = "Nihai yanıt oluşturulurken bir hata oluştu."
                    
            execution_logs.append(f"\n[Nihai Yanıt]\n{final_text}")
            break
            
        messages.append(msg)
        turn_log_lines = [f"[Turn {turn_count}] Araç Çağrıları:"]
        
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except Exception:
                fn_args = {}
                
            turn_log_lines.append(f"   -> {fn_name}({fn_args})")
            
            if fn_name == "get_weather":
                res = get_weather(**fn_args)
            elif fn_name == "convert_temperature":
                res = convert_temperature(**fn_args)
            else:
                res = json.dumps({"error": "Bilinmeyen araç"})
                
            turn_log_lines.append(f"   <- {res}")
            
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": fn_name,
                "content": res
            })
            
        execution_logs.append("\n".join(turn_log_lines))
        turn_count += 1

    return "\n\n".join(execution_logs)

# ==========================================
# 4. GRADIO ARAYÜZÜ (Örnek Sorular Eklenmiş)
# ==========================================

with gr.Blocks(title="🌤️ Tool Calling Agent (Open-Meteo Weather)") as demo:
    gr.Markdown("# 🌤️ Function Calling / Tool Calling Agent (Open-Meteo Weather)")
    gr.Markdown("Qwen3.5-9B modelinin canlı Open-Meteo Weather API ve birim dönüştürme araçlarını kullanarak çok adımlı sorguları yanıtlama akışı.")
    
    with gr.Row():
        with gr.Column():
            user_input = gr.Textbox(
                label="Soru / İstem", 
                placeholder="Örn: Ankara mı daha sıcak Londra mı, ve bu değerler Fahrenheit olarak kaç eder?",
                lines=2
            )
            
            gr.Examples(
                examples=[
                    ["Ankara mı daha sıcak Londra mı, ve bu değerler Fahrenheit olarak kaç eder?"],
                    ["Tokyo'da hava kaç fahrenayttır?"],
                    ["İstanbul mu sıcak yoksa Kahire mi?"],
                    ["Erzincan'da şu an hava kaç derece?"]
                ],
                inputs=user_input,
                label="💡 Deneyebileceğiniz Örnek Sorgular (Tıklayıp Submit'e Basın)",
                cache_examples=False
            )
            
            with gr.Row():
                submit_btn = gr.Button("Submit", variant="primary")
                clear_btn = gr.Button("Clear")
            
        with gr.Column():
            output_box = gr.Textbox(
                label="Çalışma Adımları ve Nihai Yanıt (Execution Log)", 
                lines=15
            )
    
    submit_btn.click(fn=run_agent, inputs=user_input, outputs=output_box)
    user_input.submit(fn=run_agent, inputs=user_input, outputs=output_box)
    clear_btn.click(fn=lambda: ("", ""), outputs=[user_input, output_box])

if __name__ == "__main__":
    demo.launch()