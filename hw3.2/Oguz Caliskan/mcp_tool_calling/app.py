"""
Sondaj Malzeme Depo Yönetim Asistanı - Hugging Face Space (Gradio SDK + ZeroGPU).

Model, gerektiğinde tools.py'deki fonksiyonları (gerçek SQLite veritabanına karşı
çalışan) çağırarak kullanıcının depo/talep sorularını yanıtlar. Model hiçbir zaman
veritabanında olmayan bir bilgiyi "uydurmaz" - tüm cevaplar tool sonuçlarına dayanır.
"""
import os
import re
import json
import gradio as gr
import spaces
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from db import veritabanini_kur, DB_YOLU
from tools import TOOL_SCHEMAS, ARAC_SOZLUGU, veritabani_durumunu_goster

MODEL_REPO = "Qwen/Qwen3-8B"  # public model - fine-tune edilmiş Sondaj Modeli'nin aksine,
                                # domain-özel bir kilitlenmesi yok, tool-calling için daha güvenilir
HF_TOKEN = os.environ.get("HF_TOKEN") or None  # public model için zorunlu değil, ama rate limit için faydalı

SYSTEM_PROMPT = (
    "Sen bir sondaj malzeme/ekipman depo yönetim asistanısın. Kullanıcılar sana stok "
    "durumu, malzeme talebi oluşturma ve talep durumu sorgulama gibi konularda sorular "
    "sorabilir. Sana verilen araçları (tools) kullanarak SADECE gerçek veritabanı "
    "sonuçlarına dayanan cevaplar ver. Veritabanında olmayan bir malzemeyi ya da "
    "bilgiyi ASLA uydurma; bir bilgi tooldan gelmediyse, bunu bilmediğini açıkça söyle. "
    "Bir malzeme talebi oluşturmadan önce, kullanıcı tam malzeme adını vermediyse "
    "get_stok_durumu ile doğru tam adı teyit et.\n\n"
    "ÇOK ÖNEMLİ: Tool çağırırken fonksiyon adını ve parametre adlarını TAM OLARAK, "
    "harfi harfine, sana verilen şemadaki gibi kullan - kendi çevirini/tahminini "
    "üretme, İngilizce'ye çevirme. Örnek doğru bir tool çağrısı:\n"
    '<tool_call>\n{"name": "get_stok_durumu", "arguments": {"malzeme_adi": "9 5/8 casing"}}\n</tool_call>'
)

THINK_BLOCK_REGEX = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
TOOL_CALL_REGEX = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_(?:call|response)>", re.DOTALL)

print("Veritabanı hazırlanıyor...")
veritabanini_kur()
from db import DB_YOLU
print(f"[KONTROL] Veritabanı dosyası var mı: {os.path.exists(DB_YOLU)} - Yol: {DB_YOLU}")

print("Tokenizer ve model yükleniyor (CPU'da, GPU'ya taşıma ilk çağrıda yapılacak)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_REPO, token=HF_TOKEN)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_REPO, token=HF_TOKEN, torch_dtype=torch.bfloat16,
)
print("Model CPU'da hazır, ilk GPU çağrısında cuda'ya taşınacak.")
_model_cuda_da_mi = False


@spaces.GPU(duration=120)
def _uret(messages, tools=None, max_new_tokens=2048):
    global _model_cuda_da_mi
    if not _model_cuda_da_mi:
        model.to("cuda")
        _model_cuda_da_mi = True

    girdi_metni = tokenizer.apply_chat_template(
        messages, tools=tools, tokenize=False, add_generation_prompt=True,
    )
    girdi = tokenizer(girdi_metni, return_tensors="pt").to("cuda")
    with torch.no_grad():
        # NOT: no_repeat_ngram_size/yüksek repetition_penalty BURADA kullanılmıyor -
        # bu, önceki fine-tune modeldeki "format sızıntısı" sorununu çözmek için
        # eklenmişti, ama base Qwen3'te modelin "9 5/8" gibi ifadeleri muhakeme
        # sırasında tekrar etmesini YASAKLAYIP, onu anlamsız Unicode karakterlerine
        # kaçmaya zorluyordu (Myanmar/Khmer rakamları gibi). Kaldırıldı.
        cikti = model.generate(
            **girdi, max_new_tokens=max_new_tokens,
            temperature=0.3, top_p=0.9, top_k=20, do_sample=True,
        )
    yeni_tokenlar = cikti[0][girdi["input_ids"].shape[1]:]
    return tokenizer.decode(yeni_tokenlar, skip_special_tokens=True)


def _thinking_gizle(metin):
    return THINK_BLOCK_REGEX.sub("", metin).strip()


def sohbet_et(mesaj, gecmis):
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
    for tur in range(MAKS_TUR):
        cevap_metni = _uret(messages, tools=TOOL_SCHEMAS)
        print(f"\n[DEBUG - Tur {tur+1}] Modelin ham çıktısı:\n{cevap_metni}\n")

        eslesme = TOOL_CALL_REGEX.search(cevap_metni)
        if not eslesme:
            return _thinking_gizle(cevap_metni)

        messages.append({"role": "assistant", "content": _thinking_gizle(cevap_metni)})
        try:
            cagri = json.loads(eslesme.group(1))
            # Model bazen "name"/"arguments" yerine farklı dillerden benzer kelimeler
            # üretebiliyor (örn. "nama"/"argumen" - Endonezce/Malayca kökenli sızıntı).
            # Bilinen varyasyonları da kabul ederek toleranslı davranıyoruz.
            ad = cagri.get("name") or cagri.get("nama") or cagri.get("function") or cagri.get("fonksiyon")
            args = (cagri.get("arguments") or cagri.get("argumen") or cagri.get("args")
                    or cagri.get("parametreler") or {})
        except json.JSONDecodeError:
            return _thinking_gizle(cevap_metni)

        # Model geçersiz/isimsiz bir tool çağrısı ürettiyse (örn. boş {} içerik),
        # bunu modele tekrar besleyip halüsinasyona sürüklenmesine izin VERMİYORUZ -
        # hemen, dürüst bir mesajla duruyoruz.
        if not ad or ad not in ARAC_SOZLUGU:
            return ("Üzgünüm, bu isteği işlemek için gereken aracı doğru şekilde "
                     "çağıramadım. Lütfen sorunuzu biraz daha net/farklı şekilde "
                     "tekrar sorar mısınız? (örn. tam malzeme adı ya da kuyu adıyla)")

        fonksiyon = ARAC_SOZLUGU[ad]
        try:
            sonuc = fonksiyon(**args)
        except Exception as e:
            sonuc = f"Araç çalıştırılırken hata: {e}"

        print(f"[TOOL CALL] {ad}({args}) -> {sonuc}")  # log/ekran görüntüsü için
        messages.append({"role": "tool", "content": str(sonuc)})

    return "[UYARI] Maksimum tur sayısına ulaşıldı."


with gr.Blocks(title="Sondaj Depo Asistanı") as demo:
    gr.Markdown("# Sondaj Malzeme Depo Yönetim Asistanı")

    with gr.Tab("Sohbet"):
        gr.ChatInterface(
            fn=sohbet_et,
            examples=[
                "9 5/8 casing stokta var mı?",
                "SABUN-12 kuyusu için 5 adet 9 5/8 centralizer talep et",
                "Talep 1'in durumu ne?",
            ],
        )

    with gr.Tab("Veritabanı Durumu (Canlı)"):
        gr.Markdown(
            "Bu sekme, veritabanının **o anki gerçek** içeriğini gösterir - modelin "
            "yaptığı her güncelleme burada anında görünür. 'İndir' butonuyla, çalışan "
            "Space'teki güncel `depo.db` dosyasını doğrudan indirebilirsin."
        )
        yenile_butonu = gr.Button("🔄 Durumu Yenile ve İndirmeyi Hazırla")
        durum_metni = gr.Textbox(label="Veritabanı İçeriği", lines=20, interactive=False)
        indirme_butonu = gr.DownloadButton("⬇️ depo.db Dosyasını İndir")

        def _durum_ve_indirme_hazirla():
            return veritabani_durumunu_goster(), DB_YOLU

        yenile_butonu.click(fn=_durum_ve_indirme_hazirla, outputs=[durum_metni, indirme_butonu])
        demo.load(fn=_durum_ve_indirme_hazirla, outputs=[durum_metni, indirme_butonu])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)