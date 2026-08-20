import gradio as gr
import requests
import json
import re
import spaces
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct" 

print("Loading Model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16
)
print("Model Loaded!")

def get_weather(city: str) -> str:
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
    geo_response = requests.get(geo_url).json()
    
    if "results" not in geo_response:
        return json.dumps({"error": f"City '{city}' not found."})
    
    lat = geo_response["results"][0]["latitude"]
    lon = geo_response["results"][0]["longitude"]
    
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    weather_response = requests.get(weather_url).json()
    
    current = weather_response.get("current_weather", {})
    return json.dumps({
        "city": city,
        "temperature_celsius": current.get("temperature"),
        "windspeed": current.get("windspeed")
    })

def convert_temperature(value: float, to_unit: str) -> str:
    to_unit = to_unit.upper()
    if to_unit == "F":
        res = (value * 9/5) + 32
        return json.dumps({"value": round(res, 1), "unit": "F"})
    elif to_unit == "C":
        res = (value - 32) * 5/9
        return json.dumps({"value": round(res, 1), "unit": "C"})
    return json.dumps({"error": "Unknown unit. Please use 'C' or 'F'."})

available_functions = {
    "get_weather": get_weather,
    "convert_temperature": convert_temperature
}

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather and temperature of a city in Celsius.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Name of the city (e.g., Ankara, London)"
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
            "description": "Convert a temperature value to Fahrenheit (F) or Celsius (C).",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "The temperature value to convert"
                    },
                    "to_unit": {
                        "type": "string",
                        "description": "The target unit ('F' or 'C')"
                    }
                },
                "required": ["value", "to_unit"]
            }
        }
    }
]

@spaces.GPU
def chat_with_agent(user_message, history):
    model.to("cuda")
    
    messages = [{"role": "system", "content": "You are a highly capable AI assistant. Use tools when necessary to provide accurate information. Provide your final answers in Turkish."}]
    
    for human, ai in history:
        messages.append({"role": "user", "content": human})
        messages.append({"role": "assistant", "content": ai})
        
    messages.append({"role": "user", "content": user_message})
    
    output_log = ""
    
    for turn in range(3):
        text = tokenizer.apply_chat_template(messages, tools=tools_schema, add_generation_prompt=True, tokenize=False)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        
        response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        
        tool_calls = list(re.finditer(r"<tool_call>\n(.*?)\n</tool_call>", response_text, re.DOTALL))
        
        if tool_calls:
            messages.append({"role": "assistant", "content": response_text})
            
            for match in tool_calls:
                tool_json_str = match.group(1)
                try:
                    tool_data = json.loads(tool_json_str)
                    func_name = tool_data.get("name")
                    func_args = tool_data.get("arguments", {})
                    
                    output_log += f"[Turn {turn+1}] Tool Call: -> {func_name}({func_args})\n"
                    yield output_log
                    
                    if func_name in available_functions:
                        func_result = available_functions[func_name](**func_args)
                    else:
                        func_result = json.dumps({"error": "Unknown function"})
                    
                    output_log += f"[Turn {turn+1}] Tool Response: <- {func_result}\n\n"
                    yield output_log
                    
                    messages.append({"role": "tool", "name": func_name, "content": func_result})
                    
                except Exception as e:
                    output_log += f"\n[Error] Tool parsing failed: {str(e)}\n"
                    yield output_log
        else:
            final_answer = output_log + f"**[Final Response]**\n{response_text}"
            yield final_answer
            break

# Gradio UI
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Magibu Agentic Weather Assistant")
    gr.Markdown("This application processes user queries by performing real-time Tool Calling in the background using the **Open-Meteo API**.")
    
    chatbot = gr.ChatInterface(
        fn=chat_with_agent,
        title="Agentic Weather Bot",
        description="Example: 'Ankara mı daha sıcak Londra mı, ve bu değerler Fahrenheit olarak kaç eder?'",
    )

if __name__ == "__main__":
    demo.launch()
