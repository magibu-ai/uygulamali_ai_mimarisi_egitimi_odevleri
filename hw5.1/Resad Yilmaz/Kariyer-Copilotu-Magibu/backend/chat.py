import json
from datetime import date
from pathlib import Path

from ollama_client import ollama_chat
from tools import TOOLS, tool_calistir


# =========================================================
# AYARLAR
# =========================================================

MAX_TOOL_TURU = 6


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "system_prompt.md"
)


def sistem_promptunu_yukle():
    with open(
        SYSTEM_PROMPT_PATH,
        "r",
        encoding="utf-8"
    ) as dosya:
        return dosya.read().strip()


SYSTEM_PROMPT = sistem_promptunu_yukle()


def guncel_sistem_mesaji_olustur():
    """
    Sistem promptunu, çağrı anındaki güncel tarih bilgisiyle
    birlikte üretir.

    Model, mesajlarda "bugün", "dün" gibi göreli tarih ifadeleri
    gördüğünde bunu çözümlemek için gerçek zamanlı bir bilgiye
    sahip değildir. Bu bilgi verilmediğinde model ya kullanıcıya
    gereksiz yere tarihi sorar ya da bazı turlarda boş cevap
    üretip görevi tamamlayamaz. Bu yüzden güncel tarih her
    çağrıda taze şekilde sisteme eklenir (statik SYSTEM_PROMPT
    içine gömülmez, çünkü her gün değişir).
    """

    bugun = date.today().isoformat()

    return (
        f"{SYSTEM_PROMPT}\n\n"
        "## Güncel Tarih\n\n"
        f"Bugünün tarihi: {bugun}.\n\n"
        "Kullanıcı \"bugün\", \"dün\", \"yarın\", \"geçen hafta\" "
        "gibi göreli tarih ifadeleri kullandığında, bu tarihi baz "
        "alarak YYYY-MM-DD formatında kesin bir tarih hesapla ve "
        "ilgili aracı çağır. Bu durumda kullanıcıya tekrar tarih "
        "sorma."
    )
# =========================================================
# ANA CHAT FONKSİYONU
# =========================================================

def kariyer_chat(kullanici_mesaji, onceki_mesajlar=None):
    """
    Kullanıcı mesajını modele gönderir.

    Model gerekirse bir veya birden fazla tool çağırabilir.
    Tool sonuçları tekrar modele gönderilir ve model nihai
    cevabı oluşturur.

    Args:
        kullanici_mesaji (str):
            Kullanıcının mesajı.

        onceki_mesajlar (list | None):
            Önceki konuşma geçmişi.

    Returns:
        dict:
            Model cevabı, kullanılan tool'lar ve mesaj geçmişi.
    """

    # =====================================================
    # MESAJ GEÇMİŞİNİ HAZIRLA
    # =====================================================

    guncel_sistem_mesaji = {
        "role": "system",
        "content": guncel_sistem_mesaji_olustur(),
    }

    if onceki_mesajlar:
        messages = list(onceki_mesajlar)

        # Sistem mesajını her turda güncel tarihle yenile;
        # geçmişte yoksa başa ekle.
        if messages and messages[0].get("role") == "system":
            messages[0] = guncel_sistem_mesaji
        else:
            messages.insert(0, guncel_sistem_mesaji)

    else:
        messages = [guncel_sistem_mesaji]

    # Kullanıcı mesajını ekle
    messages.append(
        {
            "role": "user",
            "content": kullanici_mesaji,
        }
    )

    # Frontend'de gösterebilmek için kullanılan tool'ları tut
    kullanilan_toollar = []

    # Model boş cevap verirse kaç defa yeniden denendiğini tut
    bos_cevap_sayisi = 0

    # =====================================================
    # AGENT / TOOL CALLING DÖNGÜSÜ
    # =====================================================

    for tur in range(MAX_TOOL_TURU):

        response = ollama_chat(
            messages=messages,
            tools=TOOLS,
        )

        # -------------------------------------------------
        # DEBUG
        # -------------------------------------------------
        # -------------------------------------------------
        # OLLAMA BAĞLANTI / MODEL HATASI
        # -------------------------------------------------

        if response.get("hata"):

            return {
                "basarili": False,
                "cevap": response.get(
                    "mesaj",
                    "Model ile iletişim kurulamadı.",
                ),
                "tools_used": kullanilan_toollar,
                "messages": messages,
            }

        # Ollama'nın assistant mesajını al
        assistant_message = response.get(
            "message",
            {}
        )

        if not assistant_message:

            return {
                "basarili": False,
                "cevap": "Modelden geçerli bir cevap alınamadı.",
                "tools_used": kullanilan_toollar,
                "messages": messages,
            }

        # Assistant mesajını geçmişe ekle
        messages.append(assistant_message)

        # Model tool çağırmış mı?
        tool_calls = assistant_message.get(
            "tool_calls",
            []
        )

        # =================================================
        # TOOL ÇAĞRISI YOKSA
        # =================================================

        if not tool_calls:

            final_cevap = assistant_message.get(
                "content",
                ""
            ).strip()

            # ---------------------------------------------
            # MODEL BOŞ CEVAP VERDİYSE
            # ---------------------------------------------

            if not final_cevap:

                bos_cevap_sayisi += 1

                print(
                    "⚠️ Model boş cevap verdi. "
                    "Agent döngüsü devam ettiriliyor..."
                )

                # Sonsuz boş cevap döngüsüne girmesin
                if bos_cevap_sayisi >= 2:

                    return {
                        "basarili": False,
                        "cevap": (
                            "Model görevi tamamlayamadı. "
                            "Lütfen isteğinizi tekrar deneyin."
                        ),
                        "tools_used": kullanilan_toollar,
                        "messages": messages,
                    }

                # Model ne yapacağını düşünüp tool çağırmamışsa
                # tekrar açık şekilde görevi tamamlamasını iste
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Görevi henüz tamamlamadın. "
                            "Bir araç kullanman gerekiyorsa ilgili "
                            "tool'u gerçekten çağır. "
                            "Kullanıcının isteğini tamamlamak için "
                            "gereken işlemleri yap ve yalnızca görev "
                            "tamamlandıktan sonra nihai cevabı ver."
                        ),
                    }
                )

                continue

            # ---------------------------------------------
            # NORMAL NİHAİ CEVAP
            # ---------------------------------------------

            return {
                "basarili": True,
                "cevap": final_cevap,
                "tools_used": kullanilan_toollar,
                "messages": messages,
            }

        # =================================================
        # TOOL ÇAĞRILARINI ÇALIŞTIR
        # =================================================

        for tool_call in tool_calls:

            function_info = tool_call.get(
                "function",
                {}
            )

            tool_adi = function_info.get(
                "name"
            )

            arguments = function_info.get(
                "arguments",
                {}
            )

            # Bazı modeller arguments kısmını JSON string
            # olarak gönderebilir
            if isinstance(arguments, str):

                try:
                    arguments = json.loads(arguments)

                except json.JSONDecodeError:

                    print(
                        f"❌ {tool_adi} için arguments "
                        "JSON olarak çözülemedi."
                    )

                    arguments = {}

            # Arguments None gelirse boş dict yap
            if arguments is None:
                arguments = {}

            # ---------------------------------------------
            # TERMINALDE TOOL ÇAĞRISINI GÖSTER
            # ---------------------------------------------

            print(
                f"\n🔧 Tool çağrısı: {tool_adi}"
            )

            print(
                f"📥 Parametreler: {arguments}"
            )

            # ---------------------------------------------
            # TOOL'U ÇALIŞTIR
            # ---------------------------------------------

            sonuc = tool_calistir(
                tool_adi,
                arguments,
            )

            print(
                f"📤 Tool sonucu: {sonuc}\n"
            )

            # ---------------------------------------------
            # FRONTEND İÇİN TOOL KAYDI
            # ---------------------------------------------

            kullanilan_toollar.append(
                {
                    "name": tool_adi,
                    "arguments": arguments,
                    "result": sonuc,
                }
            )

            # ---------------------------------------------
            # TOOL SONUCUNU MODELE GERİ GÖNDER
            # ---------------------------------------------

            tool_mesaji = {
                "role": "tool",
                "tool_name": tool_adi,
                "content": json.dumps(
                    sonuc,
                    ensure_ascii=False,
                ),
            }

            # Modelin ürettiği tool_call id'sini geri yansıt;
            # böylece model bu mesajın kendi çağrısının sonucu
            # olduğunu (kullanıcıdan gelen yeni bir veri değil)
            # net şekilde ilişkilendirebilir.
            tool_call_id = tool_call.get("id")

            if tool_call_id:
                tool_mesaji["tool_call_id"] = tool_call_id

            messages.append(tool_mesaji)

    # =====================================================
    # MAKSİMUM TOOL TURU AŞILDI
    # =====================================================

    return {
        "basarili": False,
        "cevap": (
            "İşlem sırasında çok fazla araç çağrısı yapıldı. "
            "Lütfen isteğinizi daha açık şekilde tekrar deneyin."
        ),
        "tools_used": kullanilan_toollar,
        "messages": messages,
    }


# =========================================================
# TERMINAL CHAT UYGULAMASI
# =========================================================

if __name__ == "__main__":

    print("\n" + "=" * 55)
    print("🚀 Kariyer Copilotu")
    print("=" * 55)

    # Konuşma geçmişini tutuyoruz.
    # Böylece ileride:
    #
    # Sen: Unibank başvurum ne durumda?
    # Sen: Onu reddedildi yap.
    #
    # gibi bağlama bağlı konuşmalar da mümkün olacak.
    sohbet_gecmisi = None

    while True:

        kullanici = input(
            "\nSen: "
        ).strip()

        # Çıkış
        if kullanici.lower() in [
            "çık",
            "cik",
            "exit",
            "quit",
            "/bye",
        ]:

            print(
                "\nKariyer Copilotu: Görüşürüz! 👋"
            )

            break

        # Boş mesaj
        if not kullanici:
            continue

        # ---------------------------------------------
        # CHAT
        # ---------------------------------------------

        sonuc = kariyer_chat(
            kullanici_mesaji=kullanici,
            onceki_mesajlar=sohbet_gecmisi,
        )

        # Yeni konuşma geçmişini kaydet
        sohbet_gecmisi = sonuc.get(
            "messages",
            sohbet_gecmisi,
        )

        # ---------------------------------------------
        # CEVAP
        # ---------------------------------------------

        print(
            f"\nKariyer Copilotu: {sonuc['cevap']}"
        )