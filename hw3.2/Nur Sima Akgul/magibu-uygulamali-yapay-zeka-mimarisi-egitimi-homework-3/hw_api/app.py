"""
Kutuphane Asistani — Tool-Calling Destekli (Gradio arayuzu)
-----------------------------------------------------------
Kullanici dogal dille kitap arar, oneri ister, odunc/iade yapar.
Asistan, Groq LLM ile dogru tool'u (fonksiyonu) cagirir; SQLite veritabanindan
gercek veri okur/yazar ve internetten (Google Books) kitap konusu getirir.
Arka planda cagrilan her tool ve donen veri kullaniciya adim adim gosterilir.
"""
import os
import gradio as gr

# ZeroGPU (ucretsiz HF donanimi) icin: bir @spaces.GPU fonksiyonu bekleniyor.
# LLM cagrisi disaridan (Groq) geldigi icin GPU kullanmayiz; yine de uyumluluk
# adina spaces'i import edip decorator kullaniyoruz (varsa).
try:
    import spaces
    GPU = spaces.GPU
except Exception:
    def GPU(f=None, **k):  # spaces yoksa (yerel calisma) no-op decorator
        return (lambda x: x)(f) if f else (lambda g: g)

import db
import router

db.init_db()  # veritabanini hazirla (ilk calistirmada kitaplari yukler)


@GPU
def _yanit(user_msg, history):
    """Router'i cagirip yaniti ve arka plan adimlarini formatlar."""
    hist = []
    for h in (history or []):
        if isinstance(h, dict):
            r, c = h.get("role"), h.get("content")
            if r in ("user", "assistant") and c:
                hist.append((r, c))
        elif isinstance(h, (list, tuple)) and len(h) == 2:
            hist.append(("user", h[0])) if h[0] else None
            hist.append(("assistant", h[1])) if h[1] else None

    cevap, adimlar, katman = router.yanit_uret(user_msg, hist)

    if adimlar:
        arka = "\n".join(adimlar)
        return (f"{cevap}\n\n---\n**Arka planda yapilan islemler** _(katman: {katman})_\n"
                f"```\n{arka}\n```")
    return cevap


ORNEKLER = [
    "Merhaba, polisiye kitap önerir misin?",
    "Yerli ve ince bir polisiye olsun.",
    '"Suç ve Ceza" kitabı müsait mi?',
    '"Dune" kitabının konusu ne?',
    'Sherlock Holmes: Kızıl Dosya kitabını Ayşe için ödünç al.',
    '"Suç ve Ceza" kitabını iade et.',
]

with gr.Blocks(title="Kütüphane Asistanı") as demo:
    gr.Markdown(
        "# 📚 Kütüphane Asistanı\n"
        "Kitap arayın, öneri isteyin, ödünç alın veya iade edin. Asistan gerçek "
        "veritabanına ve internete (kitap konusu) erişir; arka planda çağırdığı "
        "araçları adım adım gösterir.\n\n"
        "*İpucu: ödünç almak için önce kitabı aratıp adını netleştirin.*"
    )
    gr.ChatInterface(fn=_yanit, examples=ORNEKLER)

if __name__ == "__main__":
    demo.launch()
