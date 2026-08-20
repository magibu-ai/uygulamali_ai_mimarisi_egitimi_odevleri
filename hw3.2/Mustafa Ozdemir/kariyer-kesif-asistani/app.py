import uuid
import logging
import gradio as gr
import spaces
import araclar
from asistan import sohbet

logger = logging.getLogger(__name__)


@spaces.GPU
def _zerogpu_yer_tutucu():
    # HF ZeroGPU calisma ortami baslangicta en az bir @spaces.GPU fonksiyonu
    # gormek ister. Bu uygulama GPU kullanmaz (tum islem dis API'lerde); bu
    # fonksiyon yalnizca o gereksinimi karsilamak icindir, hicbir yerde cagrilmaz.
    return None

TIP_ADI = {
    "R": "uygulamalı ve elle iş",
    "I": "araştırma ve analiz",
    "A": "yaratıcılık ve tasarım",
    "S": "insanlarla çalışma ve yardım",
    "E": "girişimcilik ve liderlik",
    "C": "düzen ve sistemli çalışma",
}

def testi_degerlendir(*girdiler):
    puanlar = girdiler[:-1]
    oturum = girdiler[-1]
    sonuc = araclar.holland_analiz(list(puanlar))
    tipler = sonuc["baskin_tipler"]
    if tipler:
        baskin_metin = " ve ".join(TIP_ADI[t] for t in tipler)
        baskin_satiri = f"En çok öne çıkan ilgi alanların: **{baskin_metin}**."
    else:
        baskin_metin = "dengeli (belirgin bir baskın alan yok)"
        baskin_satiri = "İlgilerin oldukça **dengeli** görünüyor — belirgin bir baskın alan çıkmadı."

    satirlar = [
        "## Sonuçların",
        baskin_satiri,
        "",
        "### Sana en uygun meslekler",
    ]
    satirlar += [f"- {m['ad']}" for m in sonuc["birincil"]]
    satirlar += ["", "### Bunlar da sana yakın olabilir"]
    satirlar += [f"- {m['ad']}" for m in sonuc["ikincil"]]
    md = "\n".join(satirlar)

    ozet = (
        f"İlgi testi sonucu. Baskın ilgi alanları: {baskin_metin}. "
        f"En uygun meslekler: {', '.join(m['ad'] for m in sonuc['birincil'][:5])}."
    )
    try:
        araclar.profil_kaydet(oturum, ozet)
    except Exception:
        logger.exception("Profil kaydedilemedi")

    isimler = [m["ad"] for m in sonuc["birincil"]] + [m["ad"] for m in sonuc["ikincil"]]
    return (
        md,
        gr.Dropdown(choices=isimler, value=isimler[0], visible=True),
        gr.Button(visible=True),
    )

def _temiz_gecmis(gecmis):
    return [{"role": m["role"], "content": m["content"]} for m in (gecmis or [])]

def _guvenli_sohbet(mesaj, gecmis, oturum):
    try:
        return sohbet(mesaj, _temiz_gecmis(gecmis), kullanici_id=oturum)
    except Exception:
        logger.exception("Sohbet islenemedi")
        return "Beklenmedik bir sorun oldu. Lütfen birazdan tekrar dener misin?"

def sohbet_gonder(mesaj, gecmis, oturum):
    gecmis = gecmis or []
    goruntu = gecmis + [
        {"role": "user", "content": mesaj},
        {"role": "assistant", "content": "⏳ Yazıyorum…"},
    ]
    yield "", goruntu
    cevap = _guvenli_sohbet(mesaj, gecmis, oturum)
    goruntu[-1] = {"role": "assistant", "content": cevap}
    yield "", goruntu

def meslek_bilgi_al(meslek, gecmis, oturum):
    gecmis = gecmis or []
    soru = f"{meslek} mesleğini bana tanıt: ne iş yapar, kime uygun, geleceği ve maaşı nasıl, hangi beceriler gerekir ve nasıl başlanır?"
    goruntu = gecmis + [
        {"role": "user", "content": soru},
        {"role": "assistant", "content": f"⏳ {meslek} için araştırıyorum, birkaç saniye sürebilir…"},
    ]
    yield goruntu, gr.Tabs(selected="sohbet")
    cevap = _guvenli_sohbet(soru, gecmis, oturum)
    goruntu[-1] = {"role": "assistant", "content": cevap}
    yield goruntu, gr.Tabs(selected="sohbet")

with gr.Blocks(title="Geleceğin Meslekleri Asistanı") as arayuz:
    oturum = gr.State()

    gr.Markdown(
        "# Geleceğin Meslekleri Asistanı\n"
        "Kısa bir ilgi testiyle sana uygun meslekleri keşfet, "
        "sonra bir mesleği seçip detaylarını öğren."
    )

    with gr.Tabs() as sekmeler:
        with gr.Tab("İlgi Testi", id="test"):
            gr.Markdown(
                "Aşağıdaki 18 ifadeye, sana ne kadar uyduğunu **1 (hiç bana uygun değil)** – "
                "**5 (tam bana göre)** arası puanla. Doğru ya da yanlış cevap yok."
            )
            kaydiricilar = [
                gr.Slider(1, 5, value=3, step=1, label=f"{i}. {s['soru']}")
                for i, s in enumerate(araclar.SORULAR, 1)
            ]
            test_butonu = gr.Button("Sonuçları Gör", variant="primary")
            sonuc_kutusu = gr.Markdown()
            meslek_secim = gr.Dropdown(label="Detayını öğrenmek istediğin mesleği seç", visible=False)
            bilgi_butonu = gr.Button("Seçili meslek hakkında bilgi al", visible=False)

        with gr.Tab("Sohbet", id="sohbet"):
            gr.Markdown(
                "Testte seçtiğin mesleğin ayrıntıları buraya gelir. "
                "Dilediğini de sorabilirsin: geleceği, maaşı, hangi becerilerin gerektiği, nasıl başlanacağı…"
            )
            sohbet_kutusu = gr.Chatbot(height=420)
            mesaj_kutusu = gr.Textbox(
                label="Mesajın",
                placeholder="Örn: Grafik Tasarımcı'nın geleceği nasıl? (yazıp Enter'a bas)",
            )

    arayuz.load(lambda: uuid.uuid4().hex, outputs=oturum)

    test_butonu.click(
        testi_degerlendir,
        inputs=kaydiricilar + [oturum],
        outputs=[sonuc_kutusu, meslek_secim, bilgi_butonu],
    )
    bilgi_butonu.click(
        meslek_bilgi_al,
        inputs=[meslek_secim, sohbet_kutusu, oturum],
        outputs=[sohbet_kutusu, sekmeler],
    )
    mesaj_kutusu.submit(
        sohbet_gonder,
        inputs=[mesaj_kutusu, sohbet_kutusu, oturum],
        outputs=[mesaj_kutusu, sohbet_kutusu],
    )

if __name__ == "__main__":
    import yapilandirma
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    yapilandirma.kontrol_et()
    arayuz.launch()
