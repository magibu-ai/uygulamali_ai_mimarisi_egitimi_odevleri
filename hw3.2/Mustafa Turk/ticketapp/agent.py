"""agent.py — Ajan katmanı.

Model ile araçlar arasındaki döngüyü yönetir:

    kullanıcı sorusu
        -> model (hangi aracı çağıracağına karar verir)
        -> araç çalıştırılır (tools.py -> database.py)
        -> sonuç modele geri verilir
        -> model gerekirse yeni araç çağırır, gerekmiyorsa yanıtı üretir

Model, Hugging Face Inference Providers üzerinden çağrılır (OpenAI uyumlu API).
Bu sayede uygulamanın çalıştığı ortamda GPU gerekmez.
"""

import json
import os
from datetime import date

from openai import OpenAI

import tools

MODEL = os.environ.get("MODEL_ADI", "Qwen/Qwen2.5-72B-Instruct")
MAX_TUR = 6          # araç çağrısı döngüsünün üst sınırı (sonsuz döngü koruması)


def _istemci():
    """OpenAI uyumlu istemciyi ilk kullanımda oluşturur.

    İstemciyi modül yüklenirken oluşturmak, HF_TOKEN tanımlı değilse
    uygulamanın açılışta çökmesine yol açar. Tembel oluşturma sayesinde
    arayüz açılır ve kullanıcıya açıklayıcı bir uyarı gösterilebilir.
    """
    return OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=os.environ["HF_TOKEN"],
    )


# ---------------------------------------------------------------------------
# Sistem mesajı — halüsinasyon savunmasının ilk katmanı
# ---------------------------------------------------------------------------
SISTEM_MESAJI = f"""Sen bir uçak bileti rezervasyon asistanısın. Bugünün tarihi: {date.today().isoformat()}.

TEMEL KURAL: Verdiğin her uçuş bilgisi, fiyat, koltuk sayısı ve rezervasyon
kaydı yalnızca araçlardan dönen veriye dayanmalıdır. Hiçbir koşulda uçuş,
fiyat, saat veya PNR kodu uydurma.

Nasıl çalışırsın:
1. Kullanıcı uçuş ararsa search_flights aracını kullan.
2. Rezervasyon için sefer_id gerekir; bu değeri MUTLAKA search_flights
   sonucundan al. Tahmin etme, hatırladığını sanma.
3. YOLCU ADI: Rezervasyon için yolcu adı kullanıcı tarafından açıkça
   söylenmiş olmalıdır. Kullanıcı ad vermediyse MUTLAKA sor. Asla ad uydurma,
   örnek ad kullanma veya kullanıcının adını varsayma.
4. Rezervasyon iki aşamalıdır:
   a) book_ticket'ı önce kullanici_onayi olmadan çağır; dönen özeti
      (uçuş, tarih, yolcu, ücret) kullanıcıya göster ve onay iste.
   b) Kullanıcı açıkça onayladıktan sonra book_ticket'ı kullanici_onayi=true
      ile tekrar çağır.
5. Rezervasyon sonrası PNR kodunu kullanıcıya açıkça bildir.
6. PNR sorgusu için check_booking aracını kullan.

Araç sonuç döndürmezse:
- Uygun sefer bulunamadıysa bunu açıkça söyle, alternatif uydurma.
- Rezervasyon başarısız olduysa hatanın nedenini kullanıcıya aktar.

Yanıtların Türkçe, kısa ve net olsun. Fiyatları TL olarak, okunabilir biçimde yaz.
Yalnızca uçuş arama ve rezervasyon konularında yardımcı olursun."""


# ---------------------------------------------------------------------------
# Araç çağrı döngüsü
# ---------------------------------------------------------------------------
def calistir(soru, gecmis=None):
    """Modeli araçlarla çalıştırır.

    Parametreler:
        soru   : kullanıcının mesajı
        gecmis : önceki konuşma turları (liste). Kullanıcının
                 "ikincisini rezerve et" gibi bağlama dayalı isteklerde
                 bulunabilmesi için gereklidir.

    Dönüş: (nihai_yanit, adim_kaydi, guncel_gecmis)
    """
    if not os.environ.get("HF_TOKEN"):
        return ("HF_TOKEN tanımlı değil. Uygulama ayarlarından secret olarak "
                "eklenmelidir."), "*Yapılandırma eksik.*", (gecmis or [])

    # Konuşma geçmişi: sistem mesajı + önceki turlar + yeni soru
    mesajlar = [{"role": "system", "content": SISTEM_MESAJI}]
    mesajlar.extend(gecmis or [])
    mesajlar.append({"role": "user", "content": soru})

    kayit = []
    client = _istemci()

    for tur in range(1, MAX_TUR + 1):
        try:
            yanit = client.chat.completions.create(
                model=MODEL,
                messages=mesajlar,
                tools=tools.TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            return f"Model çağrısı başarısız: {e}", "\n".join(kayit), (gecmis or [])

        mesaj = yanit.choices[0].message

        # --- Araç çağrısı yoksa nihai yanıt üretilmiştir ---
        if not getattr(mesaj, "tool_calls", None):
            kayit.append(f"\n**[Tur {tur}] Nihai yanıt üretildi.**")
            icerik = mesaj.content or "(boş yanıt)"

            # Geçmişi güncelle: yalnızca kullanıcı ve asistan mesajları
            # saklanır; araç çağrıları bir sonraki turda gerekmez.
            yeni_gecmis = (gecmis or []) + [
                {"role": "user", "content": soru},
                {"role": "assistant", "content": icerik},
            ]
            return icerik, "\n".join(kayit), yeni_gecmis

        # --- Araç çağrıları var ---
        kayit.append(f"\n**[Tur {tur}] Araç çağrıları:**\n")

        mesajlar.append({
            "role": "assistant",
            "content": mesaj.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in mesaj.tool_calls
            ],
        })

        for tc in mesaj.tool_calls:
            ad = tc.function.name
            try:
                argumanlar = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                argumanlar = {}

            arg_metin = ", ".join(f"{k}={v!r}" for k, v in argumanlar.items())
            kayit.append(f"```\n-> {ad}({arg_metin})")

            sonuc = tools.arac_calistir(ad, argumanlar)

            # Kayıtta uzun sonuçları kısalt (arayüz okunabilir kalsın)
            sonuc_metin = json.dumps(sonuc, ensure_ascii=False)
            if len(sonuc_metin) > 500:
                sonuc_metin = sonuc_metin[:500] + " ...(kısaltıldı)"
            kayit.append(f"<- {sonuc_metin}\n```")

            mesajlar.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": ad,
                "content": json.dumps(sonuc, ensure_ascii=False),
            })

    # Döngü sınırına ulaşıldı
    return ("İşlem tamamlanamadı: araç çağrısı sınırına ulaşıldı.",
            "\n".join(kayit), (gecmis or []))
