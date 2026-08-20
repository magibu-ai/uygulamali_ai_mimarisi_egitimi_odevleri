# THY Seyahat Asistanı — tool-calling destekli Gradio sohbet arayüzü.
# Çalıştırma: python3 app.py  (OPENROUTER_API_KEY .env veya ortam değişkeninden okunur)

import json
import os
import time

import gradio as gr
from openai import OpenAI

import db
import tools

# Bu uygulama gerçek GPU işi yapmıyor (sadece OpenRouter API + CPU üzerinde küçük
# hesaplar), ama hesabın ücretsiz Hugging Face Spaces hakkı yalnızca ZeroGPU
# donanımında geçerli. ZeroGPU çalışma zamanı, en az bir @spaces.GPU fonksiyonu
# görmeden Space'i başlatmayı reddediyor; bu yüzden zararsız bir dummy fonksiyon
# tanımlıyoruz. Yerelde `spaces` paketi kurulu değilse sessizce no-op'a düşer.
try:
    import spaces
    _gpu_dekoratoru = spaces.GPU
except ImportError:
    def _gpu_dekoratoru(fn):
        return fn


@_gpu_dekoratoru
def _zero_gpu_kontrolu():
    """ZeroGPU çalışma zamanının aradığı işaret fonksiyon; gerçek iş yapmaz."""
    return True


def _env_yukle(yol=".env"):
    if not os.path.exists(yol):
        return
    with open(yol, encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            anahtar, deger = satir.split("=", 1)
            os.environ.setdefault(anahtar.strip(), deger.strip().strip("'\""))


_env_yukle()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:nitro").strip()

_istemci = None


def istemci():
    global _istemci
    if _istemci is None:
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY tanımlı değil. .env dosyasına veya ortam değişkenine ekleyin.")
        _istemci = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    return _istemci


db.kur()

PARA_BIRIMI_ONERI = {"TRY": 15000, "EUR": 500, "USD": 550, "GBP": 450}

SISTEM_PROMPTU = (
    "Sen THY'nin ic hat seyahat asistanisin. Tum ucuslar Istanbul'dan kalkar, sadece "
    "Turkiye icindeki havalimani olan sehirlere ucus satarsin. Kullanicinin bakiyesi "
    "TRY, EUR, USD veya GBP olabilir; bilet fiyatlari veritabaninda her zaman TRY'dir, "
    "bilet_al araci gerekli kur cevrimini kendisi yapar, sen ayrica cevirme. Kullanici "
    "bir yer/mekan soyleyince akisi soyle isle: "
    "1) once wikipedia_arastir ile mekanin Turkiye'de hangi sehirde oldugunu bul, "
    "2) sonra ucus_ara ile o sehre giden musait ucuslari getir ve kisaca sun, "
    "3) kullanici bir ucus secince (sefer no veya id ile), o ucusun id'siyle bilet_al'i cagir, "
    "4) bilet_al basarili donunce AYNI mesajda once tek cumlelik kisa bir tebrik yaz (PNR, "
    "odenen tutar kendi para biriminde, kalan bakiye dahil), "
    "5) hemen ardindan ayni sehir icin GUN GUN bir gezi rotasi cikar (orn. '1. Gun: ...', "
    "'2. Gun: ...'), her gun icin en az 2 aktivite/yer oner. Bu rotayi SADECE wikipedia_arastir "
    "sonucundaki gercek bilgilere dayandir; ilk sorguladigin ozet yetersizse rotayi yazmadan once "
    "wikipedia_arastir'i ayni sehir/mekan icin tekrar veya farkli bir sorguyla cagirip daha fazla "
    "detay topla. Bilet almadan once rota yazma. "
    "Bakiye sorulursa bakiye_sorgula'yi, doviz sorulursa doviz_cevir'i, saat/tarih sorulursa "
    "sehir_saat'i cagir. SADECE araclardan donen gercek veriyi kullan; DB'de olmayan bir ucusu "
    "veya bilgiyi asla uydurma. Turkce, kisa ve net konus."
)

MAKS_TUR = 6


def _arguman_coz(cagri):
    try:
        cozulen = json.loads(cagri.function.arguments or "{}")
        return cozulen if isinstance(cozulen, dict) else {}
    except json.JSONDecodeError:
        return {"_cozulemeyen": cagri.function.arguments}


def ajan_calistir(mesajlar, durum):
    """Tool-calling donguisunu calistirir; olaylari generator olarak uretir."""
    for _ in range(MAKS_TUR):
        yanit = istemci().chat.completions.create(
            model=MODEL, messages=mesajlar, tools=tools.ARAC_SEMALARI,
            tool_choice="auto", temperature=0.3,
        )
        mesaj = yanit.choices[0].message
        arac_cagrilari = list(mesaj.tool_calls or [])

        if not arac_cagrilari:
            metin = (mesaj.content or "").strip() or "(bos yanit)"
            mesajlar.append({"role": "assistant", "content": metin})
            yield {"tip": "final", "metin": metin}
            return

        mesajlar.append({
            "role": "assistant", "content": mesaj.content or "",
            "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in arac_cagrilari
            ],
        })

        for cagri in arac_cagrilari:
            argumanlar = _arguman_coz(cagri)
            yield {"tip": "arac_basladi", "arac": cagri.function.name, "argumanlar": argumanlar}

            baslangic = time.time()
            sonuc = tools.araci_calistir(cagri.function.name, argumanlar, durum)
            sure = time.time() - baslangic

            yield {
                "tip": "arac_bitti", "arac": cagri.function.name,
                "argumanlar": argumanlar, "sonuc": sonuc, "sure": sure,
            }
            mesajlar.append({
                "role": "tool", "tool_call_id": cagri.id, "name": cagri.function.name,
                "content": json.dumps(sonuc, ensure_ascii=False),
            })

    yield {"tip": "final", "metin": f"{MAKS_TUR} tur sonunda nihai cevaba ulasamadim."}


ARAC_ETIKETLERI = {
    "wikipedia_arastir": "📖 Wikipedia'da araştırıyorum",
    "sehir_saat": "🕒 Yerel saati kontrol ediyorum",
    "ucus_ara": "✈️ Uygun uçuşlara bakıyorum",
    "doviz_cevir": "💱 Kuru kontrol ediyorum",
    "bakiye_sorgula": "💳 Bakiyeni sorguluyorum",
    "bilet_al": "🎫 İşlem yapılıyor, bilet kesiliyor",
}


def _sayi_bicimle(deger):
    """1234.5 -> '1.234,50' (TR binlik/ondalik ayraci)."""
    return f"{deger:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _kisa_ozet(ad, sonuc):
    if isinstance(sonuc, dict) and "hata" in sonuc:
        return f"⚠️ {sonuc['hata']}"
    if ad == "ucus_ara":
        return f"✅ {len(sonuc.get('ucuslar', []))} uçuş buldum."
    if ad == "bilet_al":
        return (
            f"✅ Bilet alındı! PNR: {sonuc['pnr']} — ödenen "
            f"{_sayi_bicimle(sonuc['odenen'])} {sonuc['para_birimi']} "
            f"({sonuc['odenen_try']} TRY), kalan bakiye "
            f"{_sayi_bicimle(sonuc['kalan_bakiye'])} {sonuc['para_birimi']}."
        )
    if ad == "wikipedia_arastir":
        return f"✅ {sonuc.get('baslik', '')} hakkında bilgi buldum."
    return "✅ Tamamlandı."


def _arac_akis_metni(ad, argumanlar, sonuc):
    """Tool cagrisinin girdi/ciktisini oldugu gibi gosteren, seffaf bir log bloğu."""
    girdi_json = json.dumps(argumanlar or {}, ensure_ascii=False)
    cikti_json = json.dumps(sonuc, ensure_ascii=False, indent=2)
    if len(cikti_json) > 1000:
        cikti_json = cikti_json[:1000] + "\n... (kısaltıldı)"
    return (
        f"{_kisa_ozet(ad, sonuc)}\n\n"
        f"<details><summary>🔧 <code>{ad}</code> — girdi/çıktı</summary>\n\n"
        f"**Girdi:** `{girdi_json}`\n\n"
        f"**Çıktı:**\n```json\n{cikti_json}\n```\n"
        f"</details>"
    )


def _bakiye_metni(durum):
    if durum is None:
        return f"{_sayi_bicimle(PARA_BIRIMI_ONERI['TRY'])} TRY"
    return f"{_sayi_bicimle(durum['bakiye'])} {durum['para_birimi']}"


def sohbet_et(kullanici_mesaji, gecmis, mesajlar, durum):
    if not kullanici_mesaji.strip() or durum is None:
        yield gecmis, mesajlar, durum, kullanici_mesaji, _bakiye_metni(durum)
        return
    if mesajlar is None:
        mesajlar = [{"role": "system", "content": SISTEM_PROMPTU}]

    gecmis = gecmis + [{"role": "user", "content": kullanici_mesaji}]
    mesajlar.append({"role": "user", "content": kullanici_mesaji})
    yield gecmis, mesajlar, durum, "", _bakiye_metni(durum)

    try:
        for olay in ajan_calistir(mesajlar, durum):
            if olay["tip"] == "arac_basladi":
                etiket = ARAC_ETIKETLERI.get(olay["arac"], f"🔧 {olay['arac']} çalışıyor")
                gecmis = gecmis + [{"role": "assistant", "content": f"*{etiket}...*"}]
            elif olay["tip"] == "arac_bitti":
                metin = _arac_akis_metni(olay["arac"], olay["argumanlar"], olay["sonuc"])
                gecmis = gecmis + [{"role": "assistant", "content": metin}]
            elif olay["tip"] == "final":
                gecmis = gecmis + [{"role": "assistant", "content": olay["metin"]}]
            yield gecmis, mesajlar, durum, "", _bakiye_metni(durum)
    except Exception as e:
        gecmis = gecmis + [{"role": "assistant", "content": f"⚠️ Hata: {e}"}]
        yield gecmis, mesajlar, durum, "", _bakiye_metni(durum)


def _oturumu_baslat(para_birimi, tutar):
    durum = {"para_birimi": para_birimi, "bakiye": round(float(tutar), 2), "biletler": []}
    return (
        durum, _bakiye_metni(durum),
        gr.update(visible=False), gr.update(visible=True), gr.update(visible=True),
    )


with gr.Blocks(title="THY Seyahat Asistanı") as demo:
    with gr.Row():
        with gr.Column(scale=5):
            gr.Markdown(
                "# ✈️ THY Adım Adım İstanbul'dan Anadolu Programına Hoş Geldiniz!\n"
                "Geliştirilen sistem THY özelinde istediğiniz görsel mekana sizin için uygun "
                "uçuşları arar, getirir ve seyahatinizi planlar. Gittiğinizde görmeniz gereken "
                "yerleri anlatır."
            )
        with gr.Column(scale=1, min_width=160):
            bakiye_kutusu = gr.Textbox(
                label="Bakiye", value=_bakiye_metni(None), interactive=False, text_align="right",
            )

    with gr.Row() as baslangic_satiri:
        para_secimi = gr.Radio(
            list(PARA_BIRIMI_ONERI), value="TRY", label="Bakiyeni hangi para biriminde tutalım?",
        )
        tutar_girisi = gr.Number(
            value=PARA_BIRIMI_ONERI["TRY"], label="Başlangıç bakiyesi", precision=2,
        )
        baslat_btn = gr.Button("Başla", variant="primary")

    chatbot = gr.Chatbot(height=480, show_label=False, visible=False)

    with gr.Row(visible=False) as sohbet_satiri:
        kutu = gr.Textbox(
            placeholder="Örn: Kapadokya'ya gitmek istiyorum, bana bir gün planla",
            show_label=False, scale=8,
        )
        gonder_btn = gr.Button("Gönder", scale=1, variant="primary")

    mesajlar_durumu = gr.State(None)
    oturum_durumu = gr.State(None)
    girdiler = [kutu, chatbot, mesajlar_durumu, oturum_durumu]
    ciktilar = [chatbot, mesajlar_durumu, oturum_durumu, kutu, bakiye_kutusu]

    para_secimi.change(
        lambda p: PARA_BIRIMI_ONERI[p], inputs=para_secimi, outputs=tutar_girisi,
    )
    baslat_btn.click(
        _oturumu_baslat, inputs=[para_secimi, tutar_girisi],
        outputs=[oturum_durumu, bakiye_kutusu, baslangic_satiri, chatbot, sohbet_satiri],
    )

    kutu.submit(sohbet_et, inputs=girdiler, outputs=ciktilar)
    gonder_btn.click(sohbet_et, inputs=girdiler, outputs=ciktilar)

if __name__ == "__main__":
    demo.launch()
