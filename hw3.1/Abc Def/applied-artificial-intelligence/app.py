import json
import requests
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import yaml

def get_weather(latitude: float, longitude: float) -> str:
    """Fetches real-time weather metrics from the Open-Meteo API."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ["temperature_2m", "relative_humidity_2m", "wind_speed_10m"],
        "timezone": "auto"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        current = data.get("current", {})
        units = data.get("current_units", {})
        return (f"Current Weather: {current.get('temperature_2m')}{units.get('temperature_2m')}, "
                f"Humidity: {current.get('relative_humidity_2m')}{units.get('relative_humidity_2m')}, "
                f"Wind: {current.get('wind_speed_10m')} {units.get('wind_speed_10m')}.")
    except Exception as e:
        return f"Error executing tool: {str(e)}"

# Map of available system functions
TOOLS = {"get_weather": get_weather}

# System prompt giving Gemma clear instructions on how to use the tool
SYSTEM_PROMPT = """You are a helpful AI assistant equipped with tools. 
When the user asks for the weather, you MUST use the following tool syntax to call the API:
{"tool": "get_weather", "parameters": {"latitude": <float>, "longitude": <float>}}

Do not say anything else except the exact JSON block if a tool call is needed. 

Coordinates Reference Guide:
- Istanbul: lat 41.0082, lon 28.9784
- New York: lat 40.7128, lon -74.0060
- Tokyo: lat 35.6764, lon 139.6500
"""

model_id = "unsloth/gemma-4-12B-it"
tokenizer = AutoTokenizer.from_pretrained(model_id)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16),
    device_map="auto"
)


def run_agent_workflow(user_query: str):
    print(f"\n🚀 Kullanıcı Talebi: {user_query}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]

    max_tool_steps = 5
    step = 0

    while step < max_tool_steps:
        step += 1

        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

        # Girdi uzunluğunu (girdi token sayısını) tensör bazlı alıyoruz
        input_length = inputs.input_ids.shape[1]

        # return_dict_in_generate=True ile çıktıyı güvenli nesneye dönüştürüyoruz
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.1,
            return_dict_in_generate=True,  # Dilimleme hatalarını önler
            output_scores=False
        )

        # Girdi token'larını otomatik olarak kesen en temiz yaklaşım:
        generated_tokens = outputs.sequences[0][input_length:]
        ai_response = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        if not ai_response:
            print("⚠️ Kritik: Model boş döndü. Sistem promptu veya durdurma tokenı tetiklenmiş olabilir.")
            break

        if "call:" not in ai_response:
            print(f"\n✨ Ajanın Nihai Cevabı: {ai_response}")
            break
        else:
            _, func = ai_response.split("call:")
            funcname, parameters = func.split("{")
            funcname = funcname.strip()
            parameters = parameters.strip()
            parameters = "{" + parameters

            try:
                tool_call = yaml.load(parameters, Loader=yaml.SafeLoader)
                tool_name = funcname
                params = tool_call

                if tool_name in TOOLS:
                    print(f"  [Adım {step}] 🤖 Ajan Kararı: '{tool_name}' tetikleniyor...")
                    tool_output = TOOLS[tool_name](**params)
                    print(f"  [Adım {step}] 🔌 Araç Çıktısı: {tool_output}")

                    messages.append({"role": "assistant", "content": ai_response})
                    messages.append({"role": "user",
                                     "content": f"Tool '{tool_name}' returned: {tool_output}. Process this and continue."})
                    continue

            except json.JSONDecodeError:
                print(f"⚠️ Kritik: Beklenmedik sonuç {ai_response}")
                break

run_agent_workflow("What is the current weather condition in Istanbul right now?")