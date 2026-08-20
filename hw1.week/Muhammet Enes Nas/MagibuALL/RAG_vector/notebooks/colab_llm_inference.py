"""
Colab LLM Inference Script — Gemma 4 E4B

Bu script'i Google Colab'da çalıştırın.
T4 GPU seçili olmalı (Runtime > Change runtime type > T4 GPU).

İşlem sırası:
1. Gerekli kütüphaneleri yükler
2. Gemma 4 E4B modelini yükler (Unsloth ile optimize)
3. Flask API endpoint'i oluşturur
4. ngrok/cloudflared tunnel ile dışarıya açar

Local bilgisayarınızdaki .env dosyasına COLAB_LLM_URL'i yapıştırın.
"""

# ============================================================
# 1. KURULUM
# ============================================================
# !pip install -q unsloth flask pyngrok

# ============================================================
# 2. MODEL YÜKLEME
# ============================================================

from unsloth import FastLanguageModel
import torch

MODEL_NAME = "unsloth/gemma-4-E4B-it"
MAX_SEQ_LENGTH = 4096
DTYPE = None  # Otomatik (T4'te float16 kullanır)
LOAD_IN_4BIT = True  # VRAM tasarrufu için

print("Model yükleniyor...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=DTYPE,
    load_in_4bit=LOAD_IN_4BIT,
)

FastLanguageModel.for_inference(model)
print(f"Model yüklendi: {MODEL_NAME}")

# ============================================================
# 3. CEVAP ÜRETME FONKSİYONU
# ============================================================

def generate_response(prompt, system_prompt="", max_new_tokens=1024, temperature=0.3, top_p=0.9):
    """
    Verilen prompt ile model cevabı üretir.

    Args:
        prompt: Kullanıcı prompt'u (context + soru içerir).
        system_prompt: Sistem talimatı.
        max_new_tokens: Maksimum üretilecek token sayısı.
        temperature: Üretim sıcaklığı.
        top_p: Top-p sampling.

    Returns:
        str: Model cevabı.
    """
    # Gemma 4 chat template (multimodal uyumluluğu ve fallback ile)
    user_content = prompt
    if system_prompt:
        user_content = f"{system_prompt}\n\n{prompt}"

    try:
        # Gemma 4 multimodal template formatı (content list of dicts)
        messages = [{"role": "user", "content": [{"type": "text", "text": user_content}]}]
        input_ids = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(model.device)
    except Exception:
        # Manuel Gemma prompt formatı (fallback)
        raw_prompt = f"<start_of_turn>user\n{user_content}<end_of_turn>\n<start_of_turn>model\n"
        input_ids = tokenizer(raw_prompt, return_tensors="pt").input_ids.to(model.device)

    # Generate
    with torch.no_grad():
        attention_mask = (input_ids != tokenizer.pad_token_id) if tokenizer.pad_token_id is not None else torch.ones_like(input_ids)
        outputs = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
        )

    # Sadece üretilen kısmı al (input'u çıkar)
    generated_tokens = outputs[0][input_ids.shape[1]:]
    response = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    return response.strip()


# ============================================================
# 4. FLASK API ENDPOINT
# ============================================================

from flask import Flask, request, jsonify
import threading

app = Flask(__name__)

@app.route("/generate", methods=["POST"])
def generate_endpoint():
    """LLM cevap üretme endpoint'i."""
    try:
        data = request.get_json()

        prompt = data.get("prompt", "")
        system_prompt = data.get("system_prompt", "")
        max_new_tokens = data.get("max_new_tokens", 1024)
        temperature = data.get("temperature", 0.3)
        top_p = data.get("top_p", 0.9)

        if not prompt:
            return jsonify({"error": "prompt alanı gereklidir."}), 400

        response = generate_response(
            prompt=prompt,
            system_prompt=system_prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        return jsonify({
            "response": response,
            "model": MODEL_NAME,
            "status": "success",
        })

    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Sağlık kontrolü endpoint'i."""
    return jsonify({"status": "healthy", "model": MODEL_NAME})


# ============================================================
# 5. TUNNEL İLE DIŞARIYA AÇMA
# ============================================================

# ============================================================
# 5. NGROK AUTH TOKEN — BURAYA YAPIŞTIRIN
# ============================================================
# ngrok dashboard'dan kopyaladığınız token:
# https://dashboard.ngrok.com/get-started/your-authtoken

NGROK_AUTH_TOKEN = "BURAYA_NGROK_TOKENINIZI_YAPISTIRIN"  # <-- BU SATIRI DOLDURUN

# ============================================================


# Yöntem A: ngrok (pyngrok ile)
def start_with_ngrok(port=5000):
    """ngrok tunnel başlatır."""
    try:
        from pyngrok import ngrok

        # Auth token ayarla (ZORUNLU)
        if not NGROK_AUTH_TOKEN or NGROK_AUTH_TOKEN == "BURAYA_NGROK_TOKENINIZI_YAPISTIRIN":
            print("❌ NGROK_AUTH_TOKEN ayarlanmamış! Script'in üstündeki değişkeni doldurun.")
            return None

        ngrok.set_auth_token(NGROK_AUTH_TOKEN)

        public_url = ngrok.connect(port)
        print(f"\n{'='*60}")
        print(f"🌐 ngrok tunnel açıldı!")
        print(f"📡 Public URL: {public_url}")
        print(f"\n💡 Bu URL'i local makinenizdeki .env dosyasına ekleyin:")
        print(f"   COLAB_LLM_URL={public_url}/generate")
        print(f"{'='*60}\n")
        return public_url

    except Exception as e:
        print(f"⚠️ ngrok başlatılamadı: {e}")
        print("cloudflared ile deneniyor...")
        return None


# Yöntem B: cloudflared (ngrok çalışmazsa otomatik fallback)
def start_with_cloudflared(port=5000):
    """cloudflared tunnel başlatır (ngrok alternatifi, token gerektirmez)."""
    import subprocess
    import time as _time

    print("☁️ cloudflared tunnel başlatılıyor...")
    # Colab'da cloudflared'ı yükle
    subprocess.run(
        ["wget", "-q", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "-O", "/tmp/cloudflared"],
        check=True,
    )
    subprocess.run(["chmod", "+x", "/tmp/cloudflared"], check=True)

    proc = subprocess.Popen(
        ["/tmp/cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # URL'in oluşmasını bekle
    _time.sleep(5)
    output = proc.stderr.read(4096).decode()
    import re
    urls = re.findall(r'https://[\w-]+\.trycloudflare\.com', output)
    if urls:
        public_url = urls[0]
        print(f"\n{'='*60}")
        print(f"☁️ cloudflared tunnel açıldı!")
        print(f"📡 Public URL: {public_url}")
        print(f"\n💡 Bu URL'i local makinenizdeki .env dosyasına ekleyin:")
        print(f"   COLAB_LLM_URL={public_url}/generate")
        print(f"{'='*60}\n")
        return public_url
    else:
        print("cloudflared URL alınamadı. Loglara bakın.")
        return None


# ============================================================
# 6. SUNUCUYU BAŞLAT
# ============================================================

PORT = 5000

# Tunnel başlat (önce ngrok, başarısız olursa cloudflared)
url = start_with_ngrok(PORT)
if url is None:
    url = start_with_cloudflared(PORT)

# Flask sunucusunu başlat
print(f"Flask sunucusu port {PORT}'da başlatılıyor...")
app.run(host="0.0.0.0", port=PORT)
