"""
Eczane Sipariş & Prospektüs Asistanı — Ana Uygulama
Hugging Face Space (ZeroGPU) Uyumlu
"""

# --- ZeroGPU Uyumluğu (torch'tan ÖNCE import edilmeli) ---
try:
    import spaces
    HAS_SPACES = True
except ImportError:
    HAS_SPACES = False
    class spaces:
        @staticmethod
        def GPU(func):
            return func

import json
import re
import os

import gradio as gr
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from db import init_db, list_drugs
from seed_db import seed
from tools import TOOL_DEFINITIONS, route_tool_call

# Veritabanını ve başlangıç ilaçlarını yükle
init_db()
seed()

MODEL_ID = "menesnas/gemma_4_pharmacy_merged"

print(f"[INFO] Model yukleniyor: {MODEL_ID}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

try:
    from transformers import BitsAndBytesConfig
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
    )
    print("[OK] Model 4-bit quantization ile yuklendi!")
except Exception as e:
    print(f"[WARN] 4-bit yukleme basarisiz ({e}), float16 deneniyor...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    print("[OK] Model float16 ile yuklendi!")


SYSTEM_PROMPT = """Sen bir eczane sipariş asistanısın. Sana verilen araçlardan başka hiçbir bilgi kaynağın yok.
Kullanıcı ilaç bilgisi sorarsa, şikayet/semptom belirtip öneri isterse, sipariş vermek isterse veya sipariş durumu sorarsa, SADECE aşağıdaki JSON formatlarından birini üret. Başka hiçbir şey yazma.

Araçların:
1. get_drug_info: Belirli bir ilacın (örn. Parol, Majezik) stok ve prospektüs bilgisini getirir.
2. search_by_symptom: Şikayet/semptoma (örn. baş dönmesi, ateş, mide yanması) uygun ilaçları arar.
3. create_order: Sipariş oluşturur.
4. check_order_status: Sipariş durumunu sorgular.

Örnek 1:
Kullanıcı: "Parol var mı, stokta mı?"
Sen: {"name": "get_drug_info", "arguments": {"drug_name": "Parol"}}

Örnek 2:
Kullanıcı: "Baş dönmesine iyi gelen ilaç var mı? Tavsiyen var mı?"
Sen: {"name": "search_by_symptom", "arguments": {"symptom": "baş dönmesi"}}

Örnek 3:
Kullanıcı: "3 kutu Aferin sipariş etmek istiyorum"
Sen: {"name": "create_order", "arguments": {"drug_name": "Aferin", "quantity": 3}}

Örnek 4:
Kullanıcı: "12 numaralı siparişim nerede kaldı?"
Sen: {"name": "check_order_status", "arguments": {"order_id": 12}}

KURALLAR:
- Kullanıcı spesifik bir ilaç adı söylemediyse (örn. baş dönmesi, ateş, mide yanması dediyse) KESİNLİKLE uydurma bir ilaç adı yazma, `search_by_symptom` aracını kullan.
- İlaç/stok/sipariş ile ilgili her soruda SADECE yukarıdaki formatta JSON yaz, başka hiçbir şey yazma.
- İlaç bilgisi, stok, fiyat veya prospektüs bilgisini KENDİ BİLGİNDEN UYDURMA. Sadece tool sonucunda dönen veriyi kullan.
- İlaç/eczane ile ilgili olmayan sorularda normal Türkçe yanıt verebilirsin.
"""

RESULT_PROMPT_TEMPLATE = """Aşağıda bir araç çağrısının sonucu var. Bu sonucu kullanıcıya doğal, kibar Türkçe ile özetle.
SADECE aşağıdaki verileri kullan, kendi bilginden ek bilgi EKLEME.
Eğer sonuçta hata varsa, hatayı kullanıcıya nazikçe ilet.

Araç sonucu:
{tool_result}

Kullanıcının sorusu: {user_message}
"""


@spaces.GPU
def generate_response(prompt: str, max_new_tokens: int = 128) -> str:
    """Model'den hızlı ve kararlı yanıt üretir (HF ZeroGPU Uyumlu)."""
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id

    eos_ids = [tokenizer.eos_token_id]
    end_of_turn_id = tokenizer.convert_tokens_to_ids("<end_of_turn>")
    if isinstance(end_of_turn_id, int) and end_of_turn_id != tokenizer.unk_token_id:
        eos_ids.append(end_of_turn_id)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=pad_id,
            eos_token_id=eos_ids,
        )
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(generated, skip_special_tokens=False)

    if "<end_of_turn>" in text:
        text = text.split("<end_of_turn>")[0]
    if "<start_of_turn>" in text:
        text = text.split("<start_of_turn>")[0]

    return text.replace("<end_of_turn>", "").replace("<start_of_turn>", "").strip()


def parse_tool_call(text: str) -> dict | None:
    cleaned = text.strip()
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    match = re.search(r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}[^}]*\}', cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if "name" in parsed and "arguments" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

    for m in re.finditer(r'\{.*?\}', cleaned, re.DOTALL):
        try:
            parsed = json.loads(m.group())
            if "name" in parsed and "arguments" in parsed:
                return parsed
        except (json.JSONDecodeError, KeyError):
            continue

    try:
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}") + 1
        if brace_start >= 0 and brace_end > brace_start:
            candidate = cleaned[brace_start:brace_end]
            parsed = json.loads(candidate)
            if "name" in parsed and "arguments" in parsed:
                return parsed
    except (json.JSONDecodeError, KeyError):
        pass

    return None


def process_message(user_message: str) -> tuple[str, str]:
    log_lines = []

    turn1_prompt = f"<start_of_turn>system\n{SYSTEM_PROMPT}<end_of_turn>\n<start_of_turn>user\n{user_message}<end_of_turn>\n<start_of_turn>model\n"

    log_lines.append("=" * 60)
    log_lines.append("📝 TURN 1 — Model'e gönderilen kullanıcı mesajı:")
    log_lines.append(f"   \"{user_message}\"")
    log_lines.append("")

    raw_output = generate_response(turn1_prompt, max_new_tokens=64)
    log_lines.append("🤖 Model çıktısı (Turn 1 — ham):")
    log_lines.append(f"   {raw_output}")
    log_lines.append("")

    tool_call = parse_tool_call(raw_output)

    if tool_call is None:
        log_lines.append("ℹ️  Tool call tespit edilmedi — model doğrudan yanıt veriyor.")
        return raw_output, "\n".join(log_lines)

    tool_name = tool_call["name"]
    tool_args = tool_call["arguments"]

    if "quantity" in tool_args and isinstance(tool_args["quantity"], str):
        try:
            tool_args["quantity"] = int(tool_args["quantity"])
        except ValueError:
            pass
    if "order_id" in tool_args and isinstance(tool_args["order_id"], str):
        try:
            tool_args["order_id"] = int(tool_args["order_id"])
        except ValueError:
            pass

    # --- Akıllı Halüsinasyon Önleme & Rerouting ---
    if tool_name == "get_drug_info" and "drug_name" in tool_args:
        requested_drug = tool_args["drug_name"]
        from db import find_drug, search_drugs_by_keyword
        if not find_drug(requested_drug) and not search_drugs_by_keyword(requested_drug):
            symptom_matches = search_drugs_by_keyword(user_message)
            if symptom_matches:
                log_lines.append(f"⚠️ Model '{requested_drug}' adında olmayan bir ilaç üretti.")
                log_lines.append(f"🔄 Kullanıcı sorusundan veritabanı semptom aramasına yönlendiriliyor...")
                tool_name = "search_by_symptom"
                tool_args = {"symptom": user_message}

    log_lines.append(f"🔧 Tool call tespit edildi:")
    log_lines.append(f"   Araç: {tool_name}")
    log_lines.append(f"   Argümanlar: {json.dumps(tool_args, ensure_ascii=False)}")
    log_lines.append("")

    tool_result = route_tool_call(tool_name, tool_args)
    tool_result_json = json.dumps(tool_result, ensure_ascii=False, indent=2)

    log_lines.append("📦 Tool sonucu:")
    log_lines.append(f"   {tool_result_json}")
    log_lines.append("")

    result_prompt = RESULT_PROMPT_TEMPLATE.format(
        tool_result=tool_result_json,
        user_message=user_message,
    )
    turn2_prompt = (
        f"<start_of_turn>system\n{SYSTEM_PROMPT}<end_of_turn>\n"
        f"<start_of_turn>user\n{user_message}<end_of_turn>\n"
        f"<start_of_turn>model\n{json.dumps(tool_call, ensure_ascii=False)}<end_of_turn>\n"
        f"<start_of_turn>user\n{result_prompt}<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )

    final_response = generate_response(turn2_prompt, max_new_tokens=256)

    log_lines.append("💬 TURN 2 — Model'in nihai yanıtı:")
    log_lines.append(f"   {final_response}")
    log_lines.append("=" * 60)

    return final_response, "\n".join(log_lines)


def get_drugs_table():
    drugs = list_drugs()
    if not drugs:
        return [["Veri yok", "", ""]]
    return [
        [
            d["display_name"],
            str(d["stock"]),
            f"{d['price']:.2f} ₺" if d["price"] else "—",
        ]
        for d in drugs
    ]


def chat_handler(user_message: str):
    if not user_message.strip():
        return "Lütfen bir mesaj yazın.", "", get_drugs_table()

    final_response, log_text = process_message(user_message.strip())
    drugs_table = get_drugs_table()
    return final_response, log_text, drugs_table


DISCLAIMER = (
    "⚠️ **Disclaimer:** Bu sistem akademik bir projedir; stok/fiyat verileri simülasyondur, "
    "prospektüs özetleri gerçek tıbbi tavsiye yerine geçmez."
)

CUSTOM_CSS = """
    .disclaimer { 
        background: #fff3cd; 
        border: 1px solid #ffc107; 
        border-radius: 8px; 
        padding: 12px; 
        margin-top: 16px;
        font-size: 14px;
    }
    .header-title {
        text-align: center;
        margin-bottom: 8px;
    }
"""

CUSTOM_THEME = gr.themes.Soft(
    primary_hue="teal",
    secondary_hue="blue",
)

with gr.Blocks(title="Eczane Siparis Asistani") as demo:

    gr.Markdown(
        """
        # 🏥 Eczane Sipariş & Prospektüs Asistanı
        **Model:** `menesnas/gemma_4_pharmacy_merged` (Gemma 4 — Türkçe Eczacılık Fine-Tune)
        
        İlaç bilgisi sorgulayabilir, sipariş oluşturabilir ve sipariş durumunu takip edebilirsiniz.
        """,
        elem_classes=["header-title"],
    )

    with gr.Row():
        with gr.Column(scale=2):
            user_input = gr.Textbox(
                label="💬 Mesajınız",
                placeholder='Örn: "Parol stokta var mı?", "3 kutu Aferin sipariş et", "5 numaralı sipariş ne durumda?"',
                lines=2,
            )
            send_btn = gr.Button("📤 Gönder", variant="primary", size="lg")

            response_output = gr.Textbox(
                label="🤖 Asistan Yanıtı",
                lines=6,
                interactive=False,
            )

        with gr.Column(scale=1):
            drugs_table = gr.Dataframe(
                headers=["İlaç Adı", "Stok", "Fiyat"],
                label="📋 Mevcut İlaçlar",
                value=get_drugs_table(),
                interactive=False,
                wrap=True,
            )

    with gr.Accordion("🔍 Tool Call İşlem Adımları (Log)", open=False):
        log_output = gr.Textbox(
            label="İşlem Günlüğü",
            lines=15,
            interactive=False,
        )

    gr.Markdown(DISCLAIMER, elem_classes=["disclaimer"])

    send_btn.click(
        fn=chat_handler,
        inputs=[user_input],
        outputs=[response_output, log_output, drugs_table],
    )
    user_input.submit(
        fn=chat_handler,
        inputs=[user_input],
        outputs=[response_output, log_output, drugs_table],
    )


if __name__ == "__main__":
    demo.launch(theme=CUSTOM_THEME, css=CUSTOM_CSS)
