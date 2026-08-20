# Model & Makale Kasifi — yerel Ollama uzerinde tool-calling destekli arastirma asistani.
# Calistirma: python3 app.py  (once `ollama serve` acik olmali, model .env'den okunur)

import html as html_lib
import json
import os
import time

import gradio as gr
from openai import OpenAI

import tools


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

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip()
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b-mlx").strip()
tools.GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip() or None

_istemci = None


def istemci():
    global _istemci
    if _istemci is None:
        # Ollama, OpenAI-uyumlu bir /v1 endpoint sunar; api_key gercekten kontrol edilmez.
        _istemci = OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
    return _istemci


SISTEM_PROMPTU = (
    "Sen bir teknoloji arastirma asistanisin. Kullanici sana bir alan/konu (orn. 'kucuk dil "
    "modelleri', 'retrieval augmented generation', 'ses klonlama') verdiginde su akisi izle: "
    "1) huggingface_ara ile o alandaki guncel modelleri bul, "
    "2) arxiv_ara ile ilgili akademik makaleleri bul, "
    "3) gerekirse web_ara ile genel/guncel baglam (haber, blog, karsilastirma) topla, "
    "4) github_ara ile ornek kod/uygulama repolarini bul. "
    "Her model ve makale icin KISA bir ozet ver ve ARTILARINI/EKSILERINI belirt (orn. hiz, "
    "boyut/parametre sayisi, lisans, Turkce destegi, guncellik, topluluk ilgisi). Kullanici "
    "bir ornegi denemek/gormek isterse veya kucuk bir kod parcasi calistirmak isterse "
    "kod_calistir aracini kullan; uzun surecek, dosya silen/agdan buyuk veri indiren riskli "
    "kod yazma, sadece kucuk/gosterim amacli ornekler calistir. "
    "SADECE araclardan donen gercek veriyi kullan; model/makale adi, indirme sayisi veya link "
    "uydurma — arac bulamazsa bunu acikca soyle. Her oneri icin kaynak linkini mutlaka ver. "
    "Kullanici bir arastirma plani, checklist, karsilastirma tablosu, diyagram, grafik/cizim veya "
    "benzeri yapilandirilmis/gorsel bir cikti isterse (ya da bu daha iyi bir gosterim olacaksa) "
    "artifact_goster aracini kullan; formati SINIRLAMA, ne uygunsa onu uret — checklist, tablo, "
    "kart, SVG/Canvas ile diyagram veya cizim, basit bir interaktif JS bileseni, hepsi serbest. "
    "Tek kural: html kendine yeterli olsun (inline <style>/<script>/<svg>, harici kaynak/CDN yok). "
    "Panel zaten aciksa ve guncellenmesi gerekiyorsa artifact_goster'i TAM icerikle tekrar cagir. "
    "Turkce, net ve yapilandirilmis (madde isaretli) cevap ver."
)

MAKS_TUR = 8

ARAC_ETIKETLERI = {
    "web_ara": "🔍 Web'de arıyorum",
    "huggingface_ara": "🤗 Hugging Face'te modelleri tarıyorum",
    "arxiv_ara": "📄 arXiv'de makale arıyorum",
    "github_ara": "💻 GitHub'da örnek kod arıyorum",
    "kod_calistir": "🐍 Kodu çalıştırıyorum",
    "artifact_goster": "🧩 Panel hazırlıyorum",
}


def _artifact_iframe(html_icerik):
    """Artifact HTML'ini sandbox'li bir iframe icinde render eder.

    sandbox="allow-scripts" verilir ama allow-same-origin/allow-top-navigation VERILMEZ:
    iframe icindeki JS calisabilir (interaktiflik icin) ama ust sayfaya, cookie'lere veya
    DOM'a erisemez, yonlendirme yapamaz. Icerik LLM tarafindan uretildigi ve baglaminda
    guvenilmeyen web sonuclari da bulundugu icin bu izolasyon onemli.
    """
    if not html_icerik:
        return (
            "<div style='color:#888;padding:2.5rem;text-align:center;font-family:sans-serif;'>"
            "Henüz bir panel oluşturulmadı. Bir plan, tablo veya liste istediğinde burada görünecek."
            "</div>"
        )
    guvenli = html_lib.escape(html_icerik, quote=True)
    return (
        f'<iframe srcdoc="{guvenli}" sandbox="allow-scripts" '
        f'style="width:100%;height:640px;border:1px solid #ddd;border-radius:8px;"></iframe>'
    )


def _arguman_coz(arguman_str):
    try:
        cozulen = json.loads(arguman_str or "{}")
        return cozulen if isinstance(cozulen, dict) else {}
    except json.JSONDecodeError:
        return {"_cozulemeyen": arguman_str}


def _tool_calls_birlestir(birikim, delta_tool_calls):
    """Stream'den parca parca gelen tool_call delta'larini index'e gore biriktirir.

    Ollama genelde tool call'i tek chunk'ta bütun gonderiyor, ama OpenAI-standart streaming
    formati argumanlari birden fazla parcaya bolebilir; index bazli birlestirme her iki
    durumda da dogru calisir.
    """
    for tc in delta_tool_calls:
        girdi = birikim.setdefault(tc.index, {"id": None, "name": None, "arguments": ""})
        if tc.id:
            girdi["id"] = tc.id
        if tc.function:
            if tc.function.name:
                girdi["name"] = tc.function.name
            if tc.function.arguments:
                girdi["arguments"] += tc.function.arguments


def ajan_calistir(mesajlar):
    """Tool-calling donguisunu AKIS (streaming) halinde calistirir; olaylari generator olarak uretir.

    Ollama'nin dusunen (thinking) modellerinde stream'de ayrik bir `reasoning` delta alani
    geliyor; bunu `content`'ten ayri yayinlayarak kullanicinin modelin dusunce surecini canli
    gormesini sagliyoruz.
    """
    for _ in range(MAKS_TUR):
        akis = istemci().chat.completions.create(
            model=MODEL, messages=mesajlar, tools=tools.ARAC_SEMALARI,
            tool_choice="auto", temperature=0.3, stream=True,
        )

        dusunce, icerik = "", ""
        tool_calls_birikimi = {}
        dusunce_bitti_yayinlandi = False

        for parca in akis:
            delta = parca.choices[0].delta

            if getattr(delta, "reasoning", None):
                dusunce += delta.reasoning
                yield {"tip": "dusunce_parca", "guncel": dusunce}

            if delta.content:
                if dusunce and not dusunce_bitti_yayinlandi:
                    yield {"tip": "dusunce_bitti", "tam": dusunce}
                    dusunce_bitti_yayinlandi = True
                icerik += delta.content
                yield {"tip": "icerik_parca", "guncel": icerik}

            if delta.tool_calls:
                if dusunce and not dusunce_bitti_yayinlandi:
                    yield {"tip": "dusunce_bitti", "tam": dusunce}
                    dusunce_bitti_yayinlandi = True
                _tool_calls_birlestir(tool_calls_birikimi, delta.tool_calls)

        if dusunce and not dusunce_bitti_yayinlandi:
            yield {"tip": "dusunce_bitti", "tam": dusunce}

        if not tool_calls_birikimi:
            metin = icerik.strip() or "(bos yanit)"
            mesajlar.append({"role": "assistant", "content": metin})
            yield {"tip": "final", "metin": metin}
            return

        sirali_cagrilar = [tool_calls_birikimi[i] for i in sorted(tool_calls_birikimi)]
        mesajlar.append({
            "role": "assistant", "content": icerik or "",
            "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in sirali_cagrilar
            ],
        })

        for tc in sirali_cagrilar:
            argumanlar = _arguman_coz(tc["arguments"])
            yield {"tip": "arac_basladi", "arac": tc["name"], "argumanlar": argumanlar}

            baslangic = time.time()
            sonuc = tools.araci_calistir(tc["name"], argumanlar)
            sure = time.time() - baslangic

            yield {
                "tip": "arac_bitti", "arac": tc["name"],
                "argumanlar": argumanlar, "sonuc": sonuc, "sure": sure,
            }
            mesajlar.append({
                "role": "tool", "tool_call_id": tc["id"], "name": tc["name"],
                "content": json.dumps(sonuc, ensure_ascii=False),
            })

    yield {"tip": "final", "metin": f"{MAKS_TUR} tur sonunda nihai cevaba ulasamadim."}


def _kisa_ozet(ad, sonuc):
    if isinstance(sonuc, dict) and "hata" in sonuc:
        return f"⚠️ {sonuc['hata']}"
    if ad == "huggingface_ara":
        return f"✅ {len(sonuc.get('modeller', []))} model buldum."
    if ad == "arxiv_ara":
        return f"✅ {len(sonuc.get('makaleler', []))} makale buldum."
    if ad == "github_ara":
        return f"✅ {len(sonuc.get('repolar', []))} repo buldum."
    if ad == "web_ara":
        return f"✅ {len(sonuc.get('sonuclar', []))} web sonucu buldum."
    if ad == "kod_calistir":
        return "✅ Kod çalıştırıldı." if sonuc.get("donus_kodu") == 0 else "⚠️ Kod hata ile bitti."
    return "✅ Tamamlandı."


def _arac_akis_metni(ad, argumanlar, sonuc):
    """Tool cagrisinin girdi/ciktisini oldugu gibi gosteren, seffaf bir log bloğu."""
    girdi_json = json.dumps(argumanlar or {}, ensure_ascii=False)
    cikti_json = json.dumps(sonuc, ensure_ascii=False, indent=2)
    if len(cikti_json) > 1500:
        cikti_json = cikti_json[:1500] + "\n... (kısaltıldı)"
    return (
        f"{_kisa_ozet(ad, sonuc)}\n\n"
        f"<details><summary>🔧 <code>{ad}</code> — girdi/çıktı</summary>\n\n"
        f"**Girdi:** `{girdi_json}`\n\n"
        f"**Çıktı:**\n```json\n{cikti_json}\n```\n"
        f"</details>"
    )


DUSUNCE_ONIZLEME_LIMIT = 800


def _dusunce_onizleme(dusunce):
    """Canli akis sirasinda dusunce metnini son N karakterle sinirlar (DOM sismesin diye)."""
    if len(dusunce) > DUSUNCE_ONIZLEME_LIMIT:
        return "…\n" + dusunce[-DUSUNCE_ONIZLEME_LIMIT:]
    return dusunce


def sohbet_et(kullanici_mesaji, gecmis, mesajlar, artifact_durumu):
    if artifact_durumu is None:
        artifact_durumu = {"baslik": None, "html": None}
    if not kullanici_mesaji.strip():
        yield gecmis, mesajlar, "", artifact_durumu, _artifact_iframe(artifact_durumu["html"])
        return
    if mesajlar is None:
        mesajlar = [{"role": "system", "content": SISTEM_PROMPTU}]

    gecmis = gecmis + [{"role": "user", "content": kullanici_mesaji}]
    mesajlar.append({"role": "user", "content": kullanici_mesaji})
    yield gecmis, mesajlar, "", artifact_durumu, _artifact_iframe(artifact_durumu["html"])

    dusunce_idx = None
    icerik_idx = None

    try:
        for olay in ajan_calistir(mesajlar):
            if olay["tip"] == "dusunce_parca":
                if dusunce_idx is None:
                    gecmis = gecmis + [{"role": "assistant", "content": ""}]
                    dusunce_idx = len(gecmis) - 1
                gecmis[dusunce_idx]["content"] = (
                    f"🤔 *Düşünüyor...*\n\n{_dusunce_onizleme(olay['guncel'])}"
                )
            elif olay["tip"] == "dusunce_bitti":
                if dusunce_idx is not None:
                    gecmis[dusunce_idx]["content"] = (
                        f"<details><summary>🤔 Düşünme süreci</summary>\n\n{olay['tam']}\n\n</details>"
                    )
                dusunce_idx = None
            elif olay["tip"] == "icerik_parca":
                if icerik_idx is None:
                    gecmis = gecmis + [{"role": "assistant", "content": ""}]
                    icerik_idx = len(gecmis) - 1
                gecmis[icerik_idx]["content"] = olay["guncel"]
            elif olay["tip"] == "arac_basladi":
                etiket = ARAC_ETIKETLERI.get(olay["arac"], f"🔧 {olay['arac']} çalışıyor")
                gecmis = gecmis + [{"role": "assistant", "content": f"*{etiket}...*"}]
            elif olay["tip"] == "arac_bitti":
                metin = _arac_akis_metni(olay["arac"], olay["argumanlar"], olay["sonuc"])
                gecmis = gecmis + [{"role": "assistant", "content": metin}]
                if olay["arac"] == "artifact_goster" and "hata" not in olay["sonuc"]:
                    artifact_durumu = {
                        "baslik": olay["sonuc"].get("baslik"),
                        "html": olay["sonuc"].get("html"),
                    }
            elif olay["tip"] == "final":
                if icerik_idx is None:
                    gecmis = gecmis + [{"role": "assistant", "content": olay["metin"]}]
                else:
                    gecmis[icerik_idx]["content"] = olay["metin"]
            yield gecmis, mesajlar, "", artifact_durumu, _artifact_iframe(artifact_durumu["html"])
    except Exception as e:
        gecmis = gecmis + [{"role": "assistant", "content": f"⚠️ Hata: {e}"}]
        yield gecmis, mesajlar, "", artifact_durumu, _artifact_iframe(artifact_durumu["html"])


with gr.Blocks(title="Model & Makale Kaşifi") as demo:
    gr.Markdown(
        "# 🔭 Model & Makale Kaşifi\n"
        "Bir alan/konu söyle (örn. *'küçük dil modelleri'*, *'ses klonlama'*, *'RAG'*), "
        "sana güncel modelleri, makaleleri, örnek kodları bulup artı/eksileriyle özetleyeyim.\n\n"
        f"*Yerel model: `{MODEL}` — Ollama üzerinden ({OLLAMA_BASE_URL})*"
    )

    with gr.Row():
        with gr.Column(scale=6):
            chatbot = gr.Chatbot(height=520, show_label=False)
            with gr.Row():
                kutu = gr.Textbox(
                    placeholder="Örn: Türkçe küçük dil modelleri (SLM) alanında güncel çalışmaları araştır",
                    show_label=False, scale=8,
                )
                gonder_btn = gr.Button("Gönder", scale=1, variant="primary")
        with gr.Column(scale=5):
            gr.Markdown("**🧩 Panel**")
            artifact_paneli = gr.HTML(value=_artifact_iframe(None))

    mesajlar_durumu = gr.State(None)
    artifact_durumu = gr.State({"baslik": None, "html": None})
    girdiler = [kutu, chatbot, mesajlar_durumu, artifact_durumu]
    ciktilar = [chatbot, mesajlar_durumu, kutu, artifact_durumu, artifact_paneli]

    kutu.submit(sohbet_et, inputs=girdiler, outputs=ciktilar)
    gonder_btn.click(sohbet_et, inputs=girdiler, outputs=ciktilar)

if __name__ == "__main__":
    demo.launch()
