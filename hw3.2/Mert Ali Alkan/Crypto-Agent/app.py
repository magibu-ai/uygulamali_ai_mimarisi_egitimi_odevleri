import gradio as gr
import json
import re
import torch
import spaces
from transformers import AutoModelForCausalLM, AutoTokenizer
from tools import TOOLS_SCHEMA, handle_tool_call
from db import get_portfolio

model_id = "Qwen/Qwen2.5-7B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

SYSTEM_PROMPT = """Sen profesyonel bir Kripto Finans Analisti ve Yatırım Danışmanısın.
Asla kendi kafandan kripto fiyatı uydurma veya tahmin etme. Eğer fiyatı bilmiyorsan, 'get_crypto_price' aracını kullan.
Eğer araç (tool) başarısız olursa (Örn: fiyat bulunamadı), kullanıcıdan tekrar denemesini iste veya işlemi iptal et. Asla tahmini fiyat üzerinden alım-satım yapma.
İşlem yapmak için daima 'execute_trade' aracını kullan.
Yanıtların kısa, net ve profesyonel olmalı. Parasal değerleri formatlı (Örn: $25,000.00) göster."""

def parse_tool_calls(text):
    pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
    matches = re.findall(pattern, text, re.DOTALL)
    calls = []
    for m in matches:
        try:
            calls.append(json.loads(m))
        except:
            pass
    return calls

@spaces.GPU
def generate_response(messages):
    text = tokenizer.apply_chat_template(
        messages,
        tools=TOOLS_SCHEMA,
        tokenize=False,
        add_generation_prompt=True
    )
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    outputs = model.generate(
        **inputs,
        max_new_tokens=512,
        do_sample=True,
        temperature=0.2
    )
    
    generated_ids = outputs[0][len(inputs.input_ids[0]):]
    return tokenizer.decode(generated_ids, skip_special_tokens=True)

def chat_interface(messages_state):
    tool_logs = []
    
    for _ in range(4): # Max 4 zincirleme tool çalıştırabilir
        response_text = generate_response(messages_state)
        tool_calls = parse_tool_calls(response_text)
        
        if not tool_calls:
            break
            
        messages_state.append({"role": "assistant", "content": response_text})
        
        for call in tool_calls:
            name = call.get("name")
            args = call.get("arguments", {})
            tool_result = handle_tool_call(name, args)
            
            log = f"> **⚙️ Sistem İşlemi:** `{name}`\n> 📥 Parametreler: `{json.dumps(args, ensure_ascii=False)}`\n> 📤 Sonuç: `{tool_result}`"
            tool_logs.append(log)
            
            messages_state.append({
                "role": "tool",
                "name": name,
                "content": str(tool_result)
            })
            
    final_output = ""
    if tool_logs:
        final_output += "\n\n".join(tool_logs) + "\n\n---\n\n"
    final_output += "🤖 **Asistan:**\n" + response_text
    
    messages_state.append({"role": "assistant", "content": response_text})
    return final_output, messages_state

def get_balance_ui():
    portfolio = get_portfolio()
    ui_text = "### 💳 Varlık Portföyü\n"
    for asset, amount in portfolio.items():
        if asset == "USDT":
            ui_text += f"- 💵 **{asset}:** $ {amount:,.2f}\n"
        else:
            ui_text += f"- 🪙 **{asset}:** {amount:,.4f}\n"
    return ui_text

css = """
.gradio-container {
    font-family: 'Inter', sans-serif;
}
"""

with gr.Blocks(title="Kripto Asistan", css=css, theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🚀 Kripto Portföy Yöneticisi")
    gr.Markdown("Kripto para piyasasını analiz eden ve sanal bakiye ile alım-satım yapabilen akıllı asistan.")
    
    messages_state = gr.State([{"role": "system", "content": SYSTEM_PROMPT}])
    
    with gr.Row():
        with gr.Column(scale=1):
            balance_panel = gr.Markdown(get_balance_ui())
            refresh_btn = gr.Button("🔄 Bakiyeyi Güncelle")
            
            gr.Markdown("---")
            gr.Markdown("### 💡 Örnek Komutlar:\n- *Param ne kadar?*\n- *BTC'nin güncel fiyatı nedir?*\n- *1000 dolarlık BTC almak istiyorum.*\n- *0.05 BTC sat.*")
            
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="Asistan", height=600)
            msg = gr.Textbox(label="Komut", placeholder="Örn: 500 dolarlık SOL almak istiyorum...")
            clear = gr.ClearButton([msg, chatbot])
            
    def user_action(user_message: str, chat_history: list, state: list):
        chat_history.append([user_message, None])
        state.append({"role": "user", "content": user_message})
        return "", chat_history, state
        
    def bot_action(chat_history: list, state: list):
        bot_response, updated_state = chat_interface(state)
        chat_history[-1][1] = bot_response
        return chat_history, get_balance_ui(), updated_state
        
    def update_balance():
        return get_balance_ui()
        
    def clear_state():
        return [{"role": "system", "content": SYSTEM_PROMPT}]
        
    msg.submit(user_action, [msg, chatbot, messages_state], [msg, chatbot, messages_state], api_name=False).then(
        bot_action, [chatbot, messages_state], [chatbot, balance_panel, messages_state], api_name=False
    )
    
    refresh_btn.click(update_balance, None, balance_panel, api_name=False)
    clear.click(clear_state, None, messages_state, api_name=False)

if __name__ == "__main__":
    demo.launch()
