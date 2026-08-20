import os
import json
from groq import Groq
import gradio as gr

from tools import ARAC_SEMALARI, ARAC_REHBERI

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "Sen Turkiye icin bir deprem bilgi asistanisin. "
    "Deprem ve konum verisi icin MUTLAKA verilen araclari kullan; "
    "asla tahmin etme veya uydurma. "
    "Arac sonuclarina dayanarak kullaniciya Turkce, kisa ve net cevap ver."
)


def deprem_asistani(kullanici_sorusu: str):
    mesajlar = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": kullanici_sorusu},
    ]
    adimlar = []          # gosterim icin: hangi turda hangi arac cagrildi
    tur = 0

    while True:
        tur += 1

        # 1) Modele sor (mesajlar + arac menusu)
        yanit = client.chat.completions.create(
            model=MODEL,
            messages=mesajlar,
            tools=ARAC_SEMALARI,
        )
        mesaj = yanit.choices[0].message

        # 2) Modelin cevabini listeye ekle (hafiza buyur)
        mesajlar.append(mesaj)

        # 3) Arac istemediyse: bu nihai cevap -> dongudan cik
        if not mesaj.tool_calls:
            return mesaj.content, adimlar

        # 4) Arac istedi: her cagriyi calistir
        for cagri in mesaj.tool_calls:
            arac_adi   = cagri.function.name
            argumanlar = json.loads(cagri.function.arguments)   # metin -> dict

            fonksiyon = ARAC_REHBERI[arac_adi]                  # rehberden bul
            sonuc     = fonksiyon(**argumanlar)                 # cagir

            adimlar.append({"tur": tur, "arac": arac_adi,
                            "argumanlar": argumanlar, "sonuc": sonuc})

            # 5) Sonucu tool mesaji olarak listeye ekle (modele geri ver)
            mesajlar.append({
                "role": "tool",
                "tool_call_id": cagri.id,
                "content": json.dumps(sonuc, ensure_ascii=False),  # dict -> metin
            })
        # dongu basa doner -> model sonuclari gorur (Turn 2, 3...)


def _adimlari_yazdir(adimlar) -> str:
    """adimlar listesini okunur bir metne cevirir (Turn 1, Turn 2...)."""
    if not adimlar:
        return "_(Arac cagrilmadi — model dogrudan cevapladi.)_"
    satirlar = []
    for a in adimlar:
        sonuc_str = str(a["sonuc"])
        if len(sonuc_str) > 300:                 # cok uzunsa kisalt
            sonuc_str = sonuc_str[:300] + " …"
        satirlar.append(f"**Turn {a['tur']}** → `{a['arac']}({a['argumanlar']})`")
        satirlar.append(f"↳ sonuç: `{sonuc_str}`")
    return "\n\n".join(satirlar)


def arayuz(soru):
    try:
        cevap, adimlar = deprem_asistani(soru)
    except Exception as hata:
        return f"⚠️ Bir hata oluştu: {hata}"
    return ("### 🔧 Araç adımları\n\n" + _adimlari_yazdir(adimlar)
            + "\n\n### 💬 Cevap\n\n" + cevap)


demo = gr.Interface(
    fn=arayuz,
    inputs=gr.Textbox(label="Sorunuz",
                      placeholder="Örn: İstanbul'a yakın son depremler?"),
    outputs=gr.Markdown(label="Sonuç"),
    title="🌍 Deprem Asistanı",
    description="Doğal dilde sorun; model USGS araçlarını çağırıp cevaplasın.",
)

if __name__ == "__main__":
    demo.launch()