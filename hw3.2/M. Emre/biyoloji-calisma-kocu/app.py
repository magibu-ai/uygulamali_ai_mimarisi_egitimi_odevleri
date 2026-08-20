"""Biyoloji Çalışma Koçu — Gradio arayüzü.

Sağ panelde, her yanıt için modelin arka planda çağırdığı araçlar ve bu
araçlardan dönen ham veri gösterilir. Amaç şeffaflık: cevabın veritabanından
mı geldiği, yoksa modelin kendi bilgisinden mi geldiği doğrudan görülebilir.

Backend seçimi: GROQ_API_KEY tanımlıysa Groq, değilse yerel Ollama kullanılır.
"""

import os
import uuid

import gradio as gr

from koc.ajan import Koc, kaydi_bicimlendir
from koc.db import VERITABANI, baglan, semayi_kur

# HF Space'in ücretsiz katmanında Gradio uygulamaları yalnızca ZeroGPU donanımında
# barındırılabiliyor ve ZeroGPU başlangıçta en az bir @spaces.GPU fonksiyonu arıyor.
# Bu uygulama çıkarımı Groq API üzerinden yaptığı için GPU kullanmaz; aşağıdaki
# fonksiyon sadece platformun bu koşulunu karşılar. Yerel çalıştırmada `spaces`
# paketi kurulu olmayabilir, bu yüzden içe aktarma isteğe bağlıdır.
try:
    import spaces

    @spaces.GPU(duration=1)
    def _zerogpu_kaydi():
        return "ok"

except ImportError:
    pass

BEKLEME_METNI = "⋯ düşünüyorum, araçları çağırıyorum"

# Şeffaflık panelindeki ham prompt ve JSON blokları uzun satırlar içeriyor.
# Varsayılan kod bloğu satır kaydırmadığı için metin sağdan kesiliyordu.
STIL = """
#arac-gunlugu pre, #arac-gunlugu code {
    white-space: pre-wrap !important;
    word-break: break-word !important;
    overflow-wrap: anywhere !important;
}
#arac-gunlugu pre { max-height: 340px; overflow-y: auto; }
#arac-gunlugu details { margin: 6px 0; }
#arac-gunlugu summary { cursor: pointer; font-weight: 600; }
"""

ORNEKLER = [
    "Mayoz nedir?",
    "Kuantum fotosentezi nedir?",
    "Bana mayoz konusundan bir soru sor",
    "Fotosentez ne demek?",
]


def backend_olustur():
    """GROQ_API_KEY varsa bulut, yoksa yerel Ollama backend'i seçer.

    HF Space'te Ollama bulunmaz; anahtar tanımlanmadıysa yerel backend'e düşüp
    bağlantı hatasıyla çökmek yerine durumu açıkça bildiririz.
    """
    if os.environ.get("GROQ_API_KEY"):
        from koc.llm.groq_backend import GroqBackend

        return GroqBackend()

    from koc.llm.ollama_backend import OllamaBackend

    yerel = OllamaBackend()
    if os.environ.get("SPACE_ID"):  # HF Space ortamında tanımlıdır
        raise RuntimeError(
            "GROQ_API_KEY tanımlı değil. Space'te yerel model çalışmadığı için "
            "Settings > Secrets bölümünden GROQ_API_KEY eklenmelidir."
        )
    return yerel


def veritabanini_hazirla():
    """Space'te veritabanı dosyası yoksa JSON kaynaklarından üretir."""
    if VERITABANI.exists():
        return
    VERITABANI.parent.mkdir(parents=True, exist_ok=True)
    baglanti = baglan()
    semayi_kur(baglanti)
    from kurulum import sorulari_aktar, terimleri_aktar

    terimleri_aktar(baglanti)
    sorulari_aktar(baglanti)


def yeni_oturum():
    return Koc(backend_olustur(), ogrenci_id=f"ogrenci_{uuid.uuid4().hex[:8]}")


def yanitla(mesaj, sohbet, koc):
    """Generator: önce kullanıcı mesajını ekrana basar, sonra cevabı üretir.

    Tek adımda döndürülseydi soru da cevapla birlikte görünürdü; model yanıtı
    birkaç saniye sürdüğü için arayüz donmuş gibi hissettiriyordu.
    """
    if not mesaj or not mesaj.strip():
        yield sohbet, koc, gr.update(), ""
        return

    if koc is None:
        try:
            koc = yeni_oturum()
        except Exception as hata:  # örn. Space'te GROQ_API_KEY tanımsız
            yield (
                (sohbet or [])
                + [
                    {"role": "user", "content": mesaj},
                    {"role": "assistant", "content": f"Sistem başlatılamadı: {hata}"},
                ],
                None,
                f"```\n{hata}\n```",
                "",
            )
            return

    # Soru anında görünsün, girdi kutusu boşalsın. Asistan balonuna görünür bir
    # bekleme metni konur; Gradio 6'da içeriği boş olan mesaj hiç çizilmiyor.
    sohbet = (sohbet or []) + [{"role": "user", "content": mesaj}]
    bekleyen = sohbet + [{"role": "assistant", "content": BEKLEME_METNI}]
    yield bekleyen, koc, kaydi_bicimlendir([], "Başlıyor", bitti=False), ""

    # Ajan adım adım ilerler; her adımda sağdaki panel canlı güncellenir.
    try:
        for durum, kayit, cevap in koc.sor_akisli(mesaj):
            if cevap is None:
                yield bekleyen, koc, kaydi_bicimlendir(kayit, durum, bitti=False), ""
            else:
                yield (
                    sohbet + [{"role": "assistant", "content": cevap}],
                    koc,
                    kaydi_bicimlendir(kayit, durum, bitti=True),
                    "",
                )
    except Exception as hata:  # arayüz çökmesin, hatayı göster
        yield (
            sohbet + [{"role": "assistant", "content": f"Bir hata oluştu: {hata}"}],
            koc,
            f"```\n{hata}\n```",
            "",
        )


def temizle():
    # Oturum tembel kurulur (None); ilk mesajda oluşturulur ve olası kurulum
    # hatası kullanıcıya sohbet içinde gösterilir.
    return [], None, "_Henüz araç çağrılmadı._", ""


with gr.Blocks(title="Biyoloji Çalışma Koçu", analytics_enabled=False) as arayuz:
    gr.Markdown(
        """# Biyoloji Çalışma Koçu

Ders kitabı sözlüğü (1000 terim) ve gerçek sınav soruları (102 soru) üzerinde çalışan,
tool-calling destekli bir asistan. **Yanıtlar yalnızca veritabanından gelen veriye dayanır** —
sözlükte olmayan bir terim sorulduğunda model tanım uydurmaz.
"""
    )

    koc_durumu = gr.State(value=None)

    with gr.Row():
        with gr.Column(scale=3):
            sohbet_kutusu = gr.Chatbot(label="Sohbet", height=460)
            girdi = gr.Textbox(
                label="Mesajın",
                placeholder="Örn: Mayoz nedir?  /  Bana mayozdan soru sor",
                lines=2,
            )
            with gr.Row():
                gonder = gr.Button("Gönder", variant="primary")
                sifirla = gr.Button("Yeni oturum")
            gr.Examples(examples=ORNEKLER, inputs=girdi, label="Deneyebileceklerin")

        with gr.Column(scale=2):
            gr.Markdown("### Arka planda ne oldu?")
            gr.Markdown(
                "_Modelin çağırdığı araçlar ve veritabanından dönen ham veri._",
                elem_id="aciklama",
            )
            arac_gunlugu = gr.Markdown(
                value="_Henüz araç çağrılmadı._", elem_id="arac-gunlugu"
            )

    gr.Markdown(
        """---
**Araçlar:** `terim_ara` (okuma) · `quiz_getir` (okuma) · `cevap_kaydet` (yazma)
&nbsp;&nbsp;|&nbsp;&nbsp; **Veritabanı:** SQLite
&nbsp;&nbsp;|&nbsp;&nbsp; [Kaynak kod](https://github.com/nyzmemre/biyoloji-calisma-kocu)
"""
    )

    # show_progress_on: ilerleme göstergesi yalnızca sohbet alanında çizilir.
    # Varsayılan davranışta tüm çıktı bileşenlerinin üzerine biniyor ve sağdaki
    # araç günlüğünde yazılarla üst üste geliyordu.
    olaylar = dict(
        fn=yanitla,
        inputs=[girdi, sohbet_kutusu, koc_durumu],
        outputs=[sohbet_kutusu, koc_durumu, arac_gunlugu, girdi],
        show_progress="minimal",
        show_progress_on=[sohbet_kutusu],
    )
    girdi.submit(**olaylar)
    gonder.click(**olaylar)
    sifirla.click(temizle, None, [sohbet_kutusu, koc_durumu, arac_gunlugu, girdi])


if __name__ == "__main__":
    veritabanini_hazirla()
    # footer_links=[]: Gradio'nun yerleşik "Settings / Use via API / Built with
    # Gradio" bağlantıları gizlenir; uygulamayla ilgileri yok.
    arayuz.launch(theme=gr.themes.Soft(), footer_links=[], css=STIL)
