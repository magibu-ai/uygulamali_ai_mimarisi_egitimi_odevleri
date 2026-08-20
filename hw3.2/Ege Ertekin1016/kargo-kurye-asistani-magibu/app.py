import gradio as gr
import json
import os
import sqlite3
import random
import spaces
from huggingface_hub import InferenceClient

# Hugging Face Token
hf_token = os.environ.get("HF_TOKEN")
client = InferenceClient("meta-llama/Llama-3.3-70B-Instruct", token=hf_token)

# 1. VERİTABANI KURULUMU
def init_db():
    """Veritabanını oluşturur ve içine test verileri ekler."""
    conn = sqlite3.connect('kargo.db')
    c = conn.cursor()
    # Tabloyu oluştur
    c.execute('''CREATE TABLE IF NOT EXISTS kargolar
                 (takip_no TEXT PRIMARY KEY, ad_soyad TEXT, adres TEXT, paket_tipi TEXT, durum TEXT)''')
    
    # Eğer tablo boşsa test verisi ekle (READ işlemi için)
    c.execute("SELECT COUNT(*) FROM kargolar")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO kargolar VALUES ('KRG123', 'Ahmet Yılmaz', 'İstanbul, Kadıköy', 'Standart', 'Dağıtıma Çıktı')")
        c.execute("INSERT INTO kargolar VALUES ('KRG456', 'Ayşe Demir', 'Ankara, Çankaya', 'Hızlı', 'Transfer Merkezinde')")
        conn.commit()
    conn.close()

init_db()

# 2. TOOL FONKSİYONLARI (READ & WRITE İŞLEMLERİ)

def kargo_sorgula(takip_no):
    """(READ) Veritabanından kargo durumunu çeker."""
    conn = sqlite3.connect('kargo.db')
    c = conn.cursor()
    c.execute("SELECT durum, ad_soyad, adres FROM kargolar WHERE takip_no=?", (takip_no.strip().upper(),))
    res = c.fetchone()
    conn.close()
    
    if res:
        return {"mesaj": "Kargo bulundu", "alici": res[1], "teslimat_adresi": res[2], "guncel_durum": res[0]}
    return {"hata": f"{takip_no} numaralı kargo sistemde bulunamadı. Lütfen numarayı kontrol edin."}

def kurye_talep_et(ad_soyad, adres, paket_tipi):
    """(WRITE) Veritabanına yeni bir kargo kaydı açar ve takip no üretir."""
    yeni_takip_no = f"KRG{random.randint(1000, 9999)}"
    
    conn = sqlite3.connect('kargo.db')
    c = conn.cursor()
    c.execute("INSERT INTO kargolar VALUES (?, ?, ?, ?, ?)", (yeni_takip_no, ad_soyad, adres, paket_tipi, "Kurye Bekleniyor"))
    conn.commit()
    conn.close()
    
    return {
        "mesaj": "Kurye talebiniz başarıyla veritabanına kaydedildi.",
        "olusturulan_takip_no": yeni_takip_no,
        "sistem_durumu": "Kurye Bekleniyor"
    }

# 3. JSON ŞEMALARI

tools = [
    {
        "type": "function",
        "function": {
            "name": "kargo_sorgula",
            "description": "Kullanıcının verdiği takip numarasına göre kargonun veritabanındaki güncel durumunu sorgular.",
            "parameters": {
                "type": "object",
                "properties": {
                    "takip_no": {"type": "string", "description": "Sorgulanacak kargonun takip numarası (Örn: KRG123)"}
                },
                "required": ["takip_no"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kurye_talep_et",
            "description": "Kullanıcının adresinden paket aldırmak için yeni bir kurye/kargo kaydı oluşturur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ad_soyad": {"type": "string", "description": "Göndericinin adı ve soyadı"},
                    "adres": {"type": "string", "description": "Kuryenin paketi teslim alacağı açık adres"},
                    "paket_tipi": {"type": "string", "description": "Paketin tipi veya boyutu (Örn: Zarf, Standart Kutu, Büyük Koli)"}
                },
                "required": ["ad_soyad", "adres", "paket_tipi"]
            }
        }
    }
]

available_functions = {
    "kargo_sorgula": kargo_sorgula,
    "kurye_talep_et": kurye_talep_et
}

# 4. AGENT DÖNGÜSÜ (HALÜSİNASYON KORUMALI VE ZEROGPU UYUMLU)

@spaces.GPU
def process_query(user_input):
    system_prompt = """Sen 'HızlıKargo' firmasının yapay zeka asistanısın.
KURALLAR:
1. Asla veritabanında olmayan bir kargo durumunu uydurma (Halüsinasyon yapma). Sadece kargo_sorgula aracından dönen veriyi kullanıcıya söyle.
2. Kullanıcı kurye çağırmak isterse kurye_talep_et aracını kullan ve dönen takip numarasını mutlaka kullanıcıya ilet.
3. Kurye çağırmak için kullanıcının adını, adresini ve paket tipini öğrenmeden aracı çalıştırma, eksik bilgi varsa sor."""

    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "user", "content": user_input})
    
    turn_count = 1
    trace_log = ""
    
    while turn_count <= 5:
        response = client.chat.completions.create(
            messages=messages,
            tools=tools,
            max_tokens=512,
        )
        
        message = response.choices[0].message
        
        safe_msg = {"role": message.role, "content": message.content or ""}
        if message.tool_calls:
            safe_msg["tool_calls"] = []
            for tc in message.tool_calls:
                safe_msg["tool_calls"].append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": json.dumps(tc.function.arguments) if not isinstance(tc.function.arguments, str) else tc.function.arguments
                    }
                })
        messages.append(safe_msg)
        
        if message.tool_calls:
            trace_log += f"\n[Tur {turn_count}] VERİTABANI İŞLEMİ (Tool Call):\n"
            
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                
                try:
                    raw_args = tool_call.function.arguments
                    func_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        
                    args_str = ", ".join([f"{k}='{v}'" for k, v in func_args.items()])
                    trace_log += f"   -> ÇALIŞTIRILAN: {func_name}({args_str})\n"
                    
                    func_to_call = available_functions[func_name]
                    result = func_to_call(**func_args)
                except Exception as e:
                    result = {"error": f"Sistemsel Hata: {str(e)}"}
                    trace_log += f"   -> HATA: {func_name}(Hatalı Parametre)\n"
                
                trace_log += f"   <- VERİTABANI YANITI: {result}\n"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": json.dumps(result)
                })
            
            turn_count += 1
        else:
            final_answer = message.content
            break
            
    if turn_count > 5:
        final_answer = "İşlem çok uzun sürdü. Lütfen tekrar deneyin."
        
    return trace_log.strip(), final_answer


# 5. GRADIO ARAYÜZÜ

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("#  Akıllı Kargo & Kurye Asistanı ")
    gr.Markdown("Bu sistem gerçek bir **SQLite veritabanı** kullanır. Kargonuzu sorgulayabilir (READ) veya yeni bir kurye talebi oluşturarak veritabanına kayıt ekleyebilirsiniz (WRITE).")
    
    with gr.Row():
        with gr.Column(scale=1):
            user_input = gr.Textbox(label="Asistana Yazın", placeholder="Örn: KRG123 numaralı kargom nerede? veya Adım Ali Veli, İzmir Konak'tan standart bir kutu için kurye çağırır mısın?", lines=3)
            submit_btn = gr.Button("Gönder", variant="primary")
        
    with gr.Row():
        with gr.Column(scale=1):
            trace_output = gr.Textbox(label="Sistem Günlüğü (Tool Calls & DB Yanıtları)", lines=12, interactive=False)
        with gr.Column(scale=1):
            final_output = gr.Textbox(label="Asistanın Cevabı", lines=12, interactive=False)
            
    submit_btn.click(fn=process_query, inputs=user_input, outputs=[trace_output, final_output])

if __name__ == "__main__":
    demo.launch()
