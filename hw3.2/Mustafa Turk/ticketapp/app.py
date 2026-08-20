"""app.py — Gradio arayüzü.

Bu dosya yalnızca kullanıcı arayüzünden sorumludur; iş mantığı içermez.
Kullanıcı girdisini agent.py'ye iletir, dönen yanıtı ve araç adımlarını
ekranda gösterir.

Katmanlar:
    app.py       — arayüz (bu dosya)
    agent.py     — model çağrısı ve araç döngüsü
    tools.py     — araç fonksiyonları ve JSON şemaları
    database.py  — SQLite işlemleri

Çalıştırma:
    export HF_TOKEN=hf_...
    python app.py
"""

import os

import gradio as gr

import agent
import database as db

# ---------------------------------------------------------------------------
# ZeroGPU uyumluluğu
# ---------------------------------------------------------------------------
# Bu uygulama GPU kullanmaz: model Hugging Face Inference Providers üzerinden
# uzaktan çağrılır, veri ise yerel SQLite veritabanından okunur. Ancak ZeroGPU
# donanımı başlangıçta en az bir @spaces.GPU fonksiyonu bekler. Aşağıdaki
# fonksiyon yalnızca bu kontrolü karşılar; hiç çağrılmaz.
try:
    import spaces

    @spaces.GPU
    def _zerogpu_kontrol():
        return None

except ImportError:
    pass          # 'spaces' paketi yalnızca Spaces ortamında bulunur


# Uygulama başlarken veritabanını hazırla (tablolar + örnek seferler)
db.hazirla()


def veritabani_durumu():
    """Arayüzde gösterilecek özet bilgi."""
    with db.baglan() as conn:
        sefer = conn.execute("SELECT COUNT(*) FROM seferler").fetchone()[0]
        koltuk = conn.execute("SELECT SUM(bos_koltuk) FROM seferler").fetchone()[0]
        rez = conn.execute("SELECT COUNT(*) FROM rezervasyonlar").fetchone()[0]
    return f"**{sefer}** sefer · **{koltuk or 0}** boş koltuk · **{rez}** rezervasyon"


# ---------------------------------------------------------------------------
# Arayüz olayları
# ---------------------------------------------------------------------------
def mesaj_gonder(mesaj, sohbet, gecmis):
    """Kullanıcı mesajını işler.

    Parametreler:
        mesaj  : kullanıcının yazdığı metin
        sohbet : Gradio Chatbot'un gösterdiği liste
        gecmis : agent.py'nin konuşma hafızası (State içinde tutulur)

    Dönüş: (temizlenmiş kutu, güncel sohbet, adım kaydı, güncel geçmiş, durum)
    """
    if not mesaj or not mesaj.strip():
        return "", sohbet, gr.update(), gecmis, veritabani_durumu()

    cevap, kayit, yeni_gecmis = agent.calistir(mesaj.strip(), gecmis)

    sohbet = (sohbet or []) + [
        {"role": "user", "content": mesaj.strip()},
        {"role": "assistant", "content": cevap},
    ]

    return "", sohbet, (kayit or "*Araç çağrılmadı.*"), yeni_gecmis, veritabani_durumu()


def sohbeti_temizle():
    """Sohbet penceresini ve konuşma hafızasını sıfırlar."""
    return [], "*Araç çağrısı bekleniyor.*", [], veritabani_durumu()


# ---------------------------------------------------------------------------
# Arayüz
# ---------------------------------------------------------------------------
ORNEKLER = [
    "İstanbul'dan Ankara'ya uçuşları listele",
    "Antalya'ya giden en ucuz uçuş hangisi?",
    "İzmir-Trabzon arası uçuş var mı?",
    "Bulduğun ilk uçuşa Mustafa Türk adına 2 kişilik bilet al",
]

with gr.Blocks(title="Uçuş Rezervasyon Asistanı") as demo:
    gr.Markdown(
        """
        # ✈️ Uçuş Rezervasyon Asistanı

        Model, sorunuza göre uygun aracı seçer, **SQLite veritabanından** gerçek
        veriyi okur ve rezervasyon yaparken **veritabanına yazar** (koltuk sayısı
        düşer). Arka planda çağrılan araçlar sağdaki panelde adım adım görünür.

        **Araçlar:** `search_flights` (okuma) · `book_ticket` (yazma) ·
        `check_booking` (okuma)
        """
    )

    durum = gr.Markdown(veritabani_durumu())
    gecmis_state = gr.State([])

    with gr.Row():
        with gr.Column(scale=3):
            sohbet = gr.Chatbot(
                label="Sohbet",
                height=420,
            )
            with gr.Row():
                girdi = gr.Textbox(
                    label="", placeholder="Örnek: İstanbul'dan Ankara'ya uçuş ara",
                    scale=5, show_label=False,
                )
                gonder = gr.Button("Gönder", variant="primary", scale=1)
            temizle = gr.Button("Sohbeti temizle", size="sm")
            gr.Examples(examples=ORNEKLER, inputs=girdi, label="Örnek sorular")

        with gr.Column(scale=2):
            gr.Markdown("### Araç çağrı adımları")
            adimlar = gr.Markdown("*Araç çağrısı bekleniyor.*")

    # Olay bağlantıları
    gonder.click(
        mesaj_gonder,
        inputs=[girdi, sohbet, gecmis_state],
        outputs=[girdi, sohbet, adimlar, gecmis_state, durum],
    )
    girdi.submit(
        mesaj_gonder,
        inputs=[girdi, sohbet, gecmis_state],
        outputs=[girdi, sohbet, adimlar, gecmis_state, durum],
    )
    temizle.click(
        sohbeti_temizle,
        outputs=[sohbet, adimlar, gecmis_state, durum],
    )

    gr.Markdown(
        f"""
        ---
        Model: `{agent.MODEL}` — Hugging Face Inference Providers üzerinden çağrılır.
        Veritabanı: yerel SQLite (`{db.VERITABANI}`).

        *Bu bir eğitim projesidir; gerçek bilet satışı yapılmaz.*
        """
    )

if __name__ == "__main__":
    demo.launch()
