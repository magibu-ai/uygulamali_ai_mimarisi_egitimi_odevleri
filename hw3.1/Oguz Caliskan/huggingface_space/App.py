"""
Sondaj Modeli - Hugging Face Space (Gradio SDK + ZeroGPU).
Ollama yerine doğrudan `transformers` ile merge edilmiş modeli yüklüyoruz, çünkü
ZeroGPU sadece Gradio SDK ile çalışıyor (Docker/Ollama bu ortamda desteklenmiyor).

İki sekme:
  1) Sohbet (Tool Calling) - ISS konumu ve hava durumu araçlarını kullanabilen genel sohbet
  2) Rapor Analizi (Structured Output) - sondaj raporunu sabit JSON şemasına döken analiz
"""
import os
import re
import json
import requests
import gradio as gr
import spaces
import torch
from enum import Enum
from pydantic import BaseModel, ValidationError
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_REPO = "uzcaliskan/kth-tekop-sondaj-model"
HF_TOKEN = os.environ.get("HF_TOKEN") or None  # boş string gelirse None'a çevir, 'Bearer ' hatasını önler

if not HF_TOKEN:
    print("[UYARI] HF_TOKEN ortam değişkeni boş/tanımsız - private repo indirilemeyecek. "
          "Space Settings > Repository secrets kısmından HF_TOKEN'ı kontrol edin.")

SYSTEM_PROMPT = (
    "Sen Qwen3 tabanlı, genel amaçlı bir dil modelisin ve Sondaj Müdürlüğü için "
    "ek olarak fine-tune edilmiş bir sondaj takip asistanısın (Sondaj Modeli). Sana "
    "araçlar (tools) verildiyse, kullanıcının isteğini karşılamak için gerektiğinde bu "
    "araçları çağır."
)

print("Tokenizer ve model yükleniyor (CPU'da, GPU'ya taşıma ilk çağrıda yapılacak)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_REPO, token=HF_TOKEN)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_REPO, token=HF_TOKEN, torch_dtype=torch.bfloat16,
)
print("Model CPU'da hazır, ilk GPU çağrısında cuda'ya taşınacak.")
_model_cuda_da_mi = False


# ------------------ ARAÇLAR (TOOLS) ------------------

def get_iss_konumu() -> str:
    """ISS'in şu anki enlem/boylam konumunu döner."""
    try:
        yanit = requests.get("http://api.open-notify.org/iss-now.json", timeout=10)
        yanit.raise_for_status()
        veri = yanit.json()
        konum = veri["iss_position"]
        return f"ISS şu anda enlem {konum['latitude']}, boylam {konum['longitude']} konumunda."
    except Exception as e:
        return f"ISS konumu alınamadı: {e}"


def get_hava_durumu(sehir: str) -> str:
    """Open-Meteo API ile (önce geocoding, sonra tahmin) verilen şehir için 5 günlük
    hava tahminini döner. Key gerektirmez, konteyner ortamlarında güvenilir çalışır."""
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": sehir, "count": 1, "language": "tr"},
            timeout=10,
        ).json()
        if not geo.get("results"):
            return f"'{sehir}' için konum bulunamadı."
        yer = geo["results"][0]
        lat, lon = yer["latitude"], yer["longitude"]

        tahmin = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto", "forecast_days": 5,
            },
            timeout=10,
        ).json()

        gunler = tahmin["daily"]["time"]
        maks = tahmin["daily"]["temperature_2m_max"]
        min_ = tahmin["daily"]["temperature_2m_min"]
        yagis = tahmin["daily"]["precipitation_sum"]

        satirlar = [f"{sehir} için 5 günlük tahmin:"]
        for i in range(len(gunler)):
            satirlar.append(f"- {gunler[i]}: {min_[i]}°C - {maks[i]}°C, yağış: {yagis[i]} mm")
        return "\n".join(satirlar)
    except Exception as e:
        return f"Hava durumu alınamadı: {e}"


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_iss_konumu",
            "description": (
                "Get the current latitude/longitude location of the International Space "
                "Station (ISS). Use this whenever the user asks where the ISS is right now, "
                "its position, or its current location. Takes no parameters."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hava_durumu",
            "description": (
                "Get the 5-day weather forecast for a city. Use this whenever the user "
                "asks about weather, temperature, or forecast conditions for a specific city."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sehir": {"type": "string", "description": "City name, e.g. 'Istanbul', 'Ankara'."},
                },
                "required": ["sehir"],
            },
        },
    },
]

ARAC_SOZLUGU = {"get_iss_konumu": get_iss_konumu, "get_hava_durumu": get_hava_durumu}

THINK_BLOCK_REGEX = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def _thinking_gizle(metin):
    """<think>...</think> bloğunu görünen cevaptan çıkarır - model thinking üretmeye
    devam eder (eğitimindeki davranışı korumak için kapatmıyoruz), ama kullanıcıya
    sadece nihai cevap gösterilir."""
    return THINK_BLOCK_REGEX.sub("", metin).strip()


TOOL_CALL_REGEX = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def _prompt_insa_et(messages, tools=None):
    """ChatML formatında prompt'u elle inşa eder - modelin kendi Jinja chat template'ine
    (tools ile uyumsuzluk hatası veriyordu) güvenmek yerine, Ollama Modelfile'ında zaten
    kanıtlanmış olan aynı formatı burada tekrar kullanıyoruz."""
    parcalar = []
    system_icerik = next((m["content"] for m in messages if m["role"] == "system"), None)

    if system_icerik or tools:
        parcalar.append("<|im_start|>system\n")
        if system_icerik:
            parcalar.append(system_icerik)
        if tools:
            tools_blok = (
                "\n\n# Tools\n\nYou may call one or more functions to assist with the user "
                "query.\n\nYou are provided with function signatures within <tools></tools> "
                "XML tags:\n<tools>\n"
            )
            for t in tools:
                tools_blok += json.dumps({"type": "function", "function": t["function"]}, ensure_ascii=False) + "\n"
            tools_blok += (
                "</tools>\n\nFor each function call, return a json object with function name "
                "and arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n"
                '{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call>'
            )
            parcalar.append(tools_blok)
        parcalar.append("<|im_end|>\n")

    for m in messages:
        if m["role"] == "system":
            continue
        elif m["role"] == "user":
            parcalar.append(f"<|im_start|>user\n{m['content']}<|im_end|>\n")
        elif m["role"] == "assistant":
            parcalar.append(f"<|im_start|>assistant\n{m['content']}<|im_end|>\n")
        elif m["role"] == "tool":
            parcalar.append(f"<|im_start|>user\n<tool_response>\n{m['content']}\n</tool_response><|im_end|>\n")

    parcalar.append("<|im_start|>assistant\n")
    return "".join(parcalar)


@spaces.GPU(duration=120)
def _uret(messages, tools=None, max_new_tokens=1024):
    """GPU gerektiren tek üretim adımı - ZeroGPU bu fonksiyon çağrıldığında GPU tahsis eder."""
    global _model_cuda_da_mi
    if not _model_cuda_da_mi:
        model.to("cuda")
        _model_cuda_da_mi = True

    girdi_metni = _prompt_insa_et(messages, tools=tools)
    girdi = tokenizer(girdi_metni, return_tensors="pt").to("cuda")
    with torch.no_grad():
        cikti = model.generate(
            **girdi, max_new_tokens=max_new_tokens,
            temperature=0.6, top_p=0.95, top_k=20, do_sample=True,
        )
    yeni_tokenlar = cikti[0][girdi["input_ids"].shape[1]:]
    return tokenizer.decode(yeni_tokenlar, skip_special_tokens=True)


# ------------------ SEKME 1: SOHBET (TOOL CALLING, agent loop) ------------------

def sohbet_et(mesaj, gecmis):
    # Gradio sürümüne göre 'gecmis' formatı değişebilir - eski sürümlerde
    # [(kullanici_msg, asistan_msg), ...], yeni sürümlerde [{"role":..., "content":...}, ...].
    # İkisini de otomatik algılayıp destekliyoruz, ChatInterface'e 'type' parametresi
    # vermeden (bazı Gradio sürümleri bu parametreyi tanımıyor).
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for oge in gecmis:
        if isinstance(oge, dict):
            messages.append({"role": oge["role"], "content": str(oge["content"])})
        else:
            kullanici_msg, asistan_msg = oge
            messages.append({"role": "user", "content": str(kullanici_msg)})
            if asistan_msg:
                messages.append({"role": "assistant", "content": str(asistan_msg)})
    messages.append({"role": "user", "content": str(mesaj)})

    MAKS_TUR = 5
    for _ in range(MAKS_TUR):
        cevap_metni = _uret(messages, tools=TOOL_SCHEMAS)

        eslesme = TOOL_CALL_REGEX.search(cevap_metni)
        if not eslesme:
            return _thinking_gizle(cevap_metni)

        messages.append({"role": "assistant", "content": _thinking_gizle(cevap_metni)})
        try:
            cagri = json.loads(eslesme.group(1))
            ad = cagri.get("name")
            args = cagri.get("arguments", {})
        except json.JSONDecodeError:
            return cevap_metni.strip()

        fonksiyon = ARAC_SOZLUGU.get(ad)
        try:
            sonuc = fonksiyon(**args) if fonksiyon else f"Bilinmeyen araç: {ad}"
        except Exception as e:
            sonuc = f"Araç çalıştırılırken hata: {e}"
        messages.append({"role": "tool", "content": str(sonuc)})

    return "[UYARI] Maksimum tur sayısına ulaşıldı."


# ------------------ SEKME 2: RAPOR ANALİZİ (STRUCTURED OUTPUT) ------------------

class KacakSeviyesi(str, Enum):
    yok = "yok"
    hafif_orta = "hafif_orta"
    siddetli = "siddetli"
    belirlenemedi = "belirlenemedi"


class CentralizerDurumu(str, Enum):
    evet = "evet"
    hayir = "hayir"
    belirlenemedi = "belirlenemedi"


class SondajRaporAnalizi(BaseModel):
    kuyu_adi: str
    guncel_faz: str
    kacak_var_mi: bool
    kacak_seviyesi: KacakSeviyesi
    centralizer_gerekli_mi: CentralizerDurumu
    ozet: str


def rapor_analiz_et(rapor_metni):
    if not rapor_metni.strip():
        return "Lütfen bir rapor metni girin."

    sema_metni = json.dumps(SondajRaporAnalizi.model_json_schema(), ensure_ascii=False)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Aşağıdaki günlük sondaj raporunu analiz et ve SADECE şu JSON şemasına "
                f"uygun bir JSON nesnesi döndür, başka hiçbir açıklama ekleme:\n\n"
                f"Şema: {sema_metni}\n\nRapor:\n{rapor_metni}"
            ),
        },
    ]

    # transformers'ta Ollama'nın 'format' parametresi gibi garanti eden bir grammar
    # kısıtlaması yok - bu yüzden prompt-tabanlı istiyoruz ve birkaç kez deneyip
    # pydantic ile doğruluyoruz (grammar-constrained değil, best-effort).
    for _ in range(3):
        ham_cevap = _uret(messages, max_new_tokens=512)
        json_eslesme = re.search(r"\{.*\}", ham_cevap, re.DOTALL)
        if json_eslesme:
            try:
                analiz = SondajRaporAnalizi.model_validate_json(json_eslesme.group(0))
                return analiz.model_dump_json(indent=2)
            except ValidationError:
                continue
    return f"[UYARI] Model 3 denemede de geçerli/şemaya uygun JSON üretemedi.\n\nSon ham cevap:\n{ham_cevap}"


# ------------------ ARAYÜZ ------------------

with gr.Blocks(title="Sondaj") as demo:
    with gr.Tab("Sohbet (Tool Calling)"):
        gr.ChatInterface(
            fn=sohbet_et,
            examples=["ISS şu an nerede?", "İstanbul'da önümüzdeki hafta hava nasıl olacak?"],
        )
    with gr.Tab("Rapor Analizi (Structured Output)"):
        girdi = gr.Textbox(label="Sondaj Raporu", lines=8, placeholder="Kuyu Adı: ...\nBölge: ...\n08:00 Durumu: ...")
        buton = gr.Button("Analiz Et")
        cikti = gr.Textbox(label="Yapılandırılmış Analiz (JSON)", lines=10)
        buton.click(fn=rapor_analiz_et, inputs=girdi, outputs=cikti)

if __name__ == "__main__":
    demo.launch()