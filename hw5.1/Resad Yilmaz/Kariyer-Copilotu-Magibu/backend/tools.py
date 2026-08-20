import inspect
from difflib import get_close_matches

import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, urlparse, parse_qs

from db import (
    basvuru_ekle,
    basvuru_ara,
    basvuru_listele,
    basvuru_guncelle,
    basvuru_istatistikleri,
    yaklasan_mulakatlari_getir,
)

from career_rag import rag_ara

# =========================================================
# WEB ARAMA
# =========================================================

def web_arama(query, sonuc_sayisi=5):
    """
    DuckDuckGo üzerinden internette arama yapar.

    Args:
        query (str): Aranacak sorgu.
        sonuc_sayisi (int): Döndürülecek maksimum sonuç sayısı.

    Returns:
        dict: Arama sonuçları.
    """

    try:
        url = "https://html.duckduckgo.com/html/"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }

        response = requests.get(
            url,
            params={"q": query},
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        sonuclar = []

        for sonuc in soup.select(".result"):
            baslik_elementi = sonuc.select_one(".result__a")
            aciklama_elementi = sonuc.select_one(".result__snippet")

            if baslik_elementi is None:
                continue

            baslik = baslik_elementi.get_text(" ", strip=True)
            link = baslik_elementi.get("href", "")
            aciklama = ""

            if aciklama_elementi:
                aciklama = aciklama_elementi.get_text(
                    " ",
                    strip=True
                )

            # DuckDuckGo yönlendirme linkinden gerçek URL'yi çıkarmaya çalış
            if link.startswith("//"):
                link = "https:" + link

            if "duckduckgo.com/l/" in link:
                try:
                    parsed = urlparse(link)
                    params = parse_qs(parsed.query)

                    if "uddg" in params:
                        link = unquote(params["uddg"][0])
                except Exception:
                    pass

            sonuclar.append(
                {
                    "baslik": baslik,
                    "link": link,
                    "aciklama": aciklama,
                }
            )

            if len(sonuclar) >= sonuc_sayisi:
                break

        if not sonuclar:
            return {
                "basarili": False,
                "mesaj": "İnternet aramasında sonuç bulunamadı.",
                "query": query,
                "sonuclar": [],
            }

        return {
            "basarili": True,
            "query": query,
            "adet": len(sonuclar),
            "sonuclar": sonuclar,
        }

    except requests.RequestException as hata:
        return {
            "basarili": False,
            "mesaj": f"İnternet araması sırasında bağlantı hatası oluştu: {str(hata)}",
            "query": query,
            "sonuclar": [],
        }

    except Exception as hata:
        return {
            "basarili": False,
            "mesaj": f"İnternet araması sırasında hata oluştu: {str(hata)}",
            "query": query,
            "sonuclar": [],
        }


# =========================================================
# TOOL WRAPPER FONKSİYONLARI
# =========================================================

def tool_web_arama(query, sonuc_sayisi=5):
    return web_arama(
        query=query,
        sonuc_sayisi=sonuc_sayisi,
    )


def tool_basvuru_ekle(
    sirket,
    pozisyon,
    basvuru_tarihi,
    durum="Başvuruldu",
    ilan_linki="",
    mulakat_tarihi=None,
    notlar="",
):
    return basvuru_ekle(
        sirket=sirket,
        pozisyon=pozisyon,
        basvuru_tarihi=basvuru_tarihi,
        durum=durum,
        ilan_linki=ilan_linki,
        mulakat_tarihi=mulakat_tarihi,
        notlar=notlar,
    )


def tool_basvuru_ara(arama):
    return basvuru_ara(arama)


def tool_basvuru_listele(
    durum=None,
    sirket=None,
    pozisyon=None,
):
    return basvuru_listele(
        durum=durum,
        sirket=sirket,
        pozisyon=pozisyon,
    )


def tool_basvuru_guncelle(
    basvuru_id,
    yeni_durum=None,
    mulakat_tarihi=None,
    notlar=None,
):
    return basvuru_guncelle(
        basvuru_id=basvuru_id,
        yeni_durum=yeni_durum,
        mulakat_tarihi=mulakat_tarihi,
        notlar=notlar,
    )


def tool_basvuru_istatistikleri():
    return basvuru_istatistikleri()


def tool_yaklasan_mulakatlari_getir(gun_sayisi=30):
    return yaklasan_mulakatlari_getir(
        gun_sayisi=gun_sayisi
    )
def tool_rag_ara(
    soru,
    top_k=5,
    kaynak=None,
):
    return rag_ara(
        soru=soru,
        top_k=top_k,
        kaynak=kaynak,
    )

# =========================================================
# OLLAMA TOOL ŞEMALARI
# =========================================================

TOOLS = [

    # -----------------------------------------------------
    # 1. WEB ARAMA
    # -----------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "web_arama",
            "description": (
                "İnternette güncel bilgi aramak için kullanılır. "
                "Şirketler, pozisyonlar, sektörler, teknolojiler, "
                "iş ilanları ve diğer güncel bilgiler hakkında "
                "arama yapabilir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "İnternette aranacak açık ve anlamlı sorgu."
                        ),
                    },
                    "sonuc_sayisi": {
                        "type": "integer",
                        "description": (
                            "Döndürülecek maksimum arama sonucu sayısı."
                        ),
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": [
                    "query"
                ],
            },
        },
    },

    # -----------------------------------------------------
    # 2. BAŞVURU EKLE
    # -----------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "basvuru_ekle",
            "description": (
                "Kullanıcının yaptığı yeni bir iş başvurusunu "
                "veritabanına kaydeder. "
                "Şirket, pozisyon ve başvuru tarihi bilinmeden "
                "bu araç çağrılmamalıdır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sirket": {
                        "type": "string",
                        "description": (
                            "Başvuru yapılan şirketin adı."
                        ),
                    },
                    "pozisyon": {
                        "type": "string",
                        "description": (
                            "Başvurulan pozisyonun adı."
                        ),
                    },
                    "basvuru_tarihi": {
                        "type": "string",
                        "description": (
                            "Başvurunun yapıldığı tarih. "
                            "YYYY-MM-DD formatında olmalıdır."
                        ),
                    },
                    "durum": {
                        "type": "string",
                        "description": (
                            "Başvurunun mevcut aşaması."
                        ),
                        "enum": [
                            "Başvuruldu",
                            "Değerlendirmede",
                            "Test Aşamasında",
                            "Mülakat",
                            "Teklif",
                            "Reddedildi",
                            "Geri Dönüş Yok",
                        ],
                    },
                    "ilan_linki": {
                        "type": "string",
                        "description": (
                            "Varsa başvurulan iş ilanının bağlantısı."
                        ),
                    },
                    "mulakat_tarihi": {
                        "type": "string",
                        "description": (
                            "Varsa mülakat tarihi. "
                            "YYYY-MM-DD formatında olmalıdır."
                        ),
                    },
                    "notlar": {
                        "type": "string",
                        "description": (
                            "Başvuruyla ilgili ek bilgiler veya notlar."
                        ),
                    },
                },
                "required": [
                    "sirket",
                    "pozisyon",
                    "basvuru_tarihi",
                ],
            },
        },
    },

    # -----------------------------------------------------
    # 3. BAŞVURU ARA
    # -----------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "basvuru_ara",
            "description": (
                "Kullanıcının geçmiş iş başvuruları arasında "
                "şirket veya pozisyon adına göre arama yapar. "
                "Belirli bir başvurunun durumunu öğrenmek için "
                "bu araç kullanılmalıdır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "arama": {
                        "type": "string",
                        "description": (
                            "Aranacak şirket veya pozisyon adı."
                        ),
                    },
                },
                "required": [
                    "arama"
                ],
            },
        },
    },

    # -----------------------------------------------------
    # 4. BAŞVURU LİSTELE
    # -----------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "basvuru_listele",
            "description": (
                "Kullanıcının iş başvurularını listeler. "
                "Başvurular durum, şirket veya pozisyon adına "
                "göre filtrelenebilir. Hiç filtre verilmezse "
                "tüm başvurular listelenir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "durum": {
                        "type": "string",
                        "description": (
                            "Başvuru durumuna göre filtre."
                        ),
                        "enum": [
                            "Başvuruldu",
                            "Değerlendirmede",
                            "Test Aşamasında",
                            "Mülakat",
                            "Teklif",
                            "Reddedildi",
                            "Geri Dönüş Yok",
                        ],
                    },
                    "sirket": {
                        "type": "string",
                        "description": (
                            "Şirket adına göre filtre."
                        ),
                    },
                    "pozisyon": {
                        "type": "string",
                        "description": (
                            "Pozisyon adına göre filtre. "
                            "Örneğin AI, Data Engineer veya "
                            "Data Analyst."
                        ),
                    },
                },
            },
        },
    },

    # -----------------------------------------------------
    # 5. BAŞVURU GÜNCELLE
    # -----------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "basvuru_guncelle",
            "description": (
                "Veritabanında bulunan mevcut bir başvurunun "
                "durumunu, mülakat tarihini veya notlarını günceller. "
                "Başvurunun veritabanı ID'si gereklidir. "
                "ID bilinmiyorsa önce basvuru_ara kullanılmalıdır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "basvuru_id": {
                        "type": "integer",
                        "description": (
                            "Güncellenecek başvurunun veritabanındaki ID'si."
                        ),
                    },
                    "yeni_durum": {
                        "type": "string",
                        "description": (
                            "Başvurunun yeni durumu."
                        ),
                        "enum": [
                            "Başvuruldu",
                            "Değerlendirmede",
                            "Test Aşamasında",
                            "Mülakat",
                            "Teklif",
                            "Reddedildi",
                            "Geri Dönüş Yok",
                        ],
                    },
                    "mulakat_tarihi": {
                        "type": "string",
                        "description": (
                            "Varsa yeni mülakat tarihi. "
                            "YYYY-MM-DD formatında olmalıdır."
                        ),
                    },
                    "notlar": {
                        "type": "string",
                        "description": (
                            "Başvuruyla ilgili yeni not."
                        ),
                    },
                },
                "required": [
                    "basvuru_id"
                ],
            },
        },
    },

    # -----------------------------------------------------
    # 6. BAŞVURU İSTATİSTİKLERİ
    # -----------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "basvuru_istatistikleri",
            "description": (
                "Kullanıcının iş başvurularının genel "
                "istatistiklerini getirir. Toplam başvuru sayısı, "
                "durumlara göre başvuru sayıları ve en çok "
                "başvurulan pozisyonlar gibi bilgileri döndürür."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },

    # -----------------------------------------------------
    # 7. YAKLAŞAN MÜLAKATLAR
    # -----------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "yaklasan_mulakatlari_getir",
            "description": (
                "Bugünden itibaren belirtilen gün sayısı "
                "içerisindeki yaklaşan iş mülakatlarını getirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gun_sayisi": {
                        "type": "integer",
                        "description": (
                            "Bugünden itibaren kaç gün ileriye "
                            "kadar mülakat aranacağı. "
                            "Örneğin 7, 14 veya 30."
                        ),
                        "minimum": 1,
                        "maximum": 365,
                    },
                },
            },
        },
    },

    # -----------------------------------------------------
    # 8. RAG ARAMA
    # -----------------------------------------------------
    {
        "type": "function",
    "function": {
        "name": "rag_ara",
        "description": (
            "Adayın CV'si ve mülakat çalışma notları içerisinde "
            "anlamsal arama yapar. Adayın deneyimleri, teknik "
            "yetenekleri, projeleri, eğitimleri veya mülakat "
            "hazırlık konuları hakkında bilgi gerektiğinde "
            "bu araç kullanılmalıdır."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "soru": {
                    "type": "string",
                    "description": (
                        "CV veya mülakat notları içerisinde "
                        "aranacak soru veya konu."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": (
                        "Getirilecek en alakalı doküman "
                        "parçası sayısı."
                    ),
                    "minimum": 1,
                    "maximum": 10,
                },
                "kaynak": {
                    "type": "string",
                    "description": (
                        "Aramanın hangi kaynakta yapılacağını "
                        "belirtir. Belirtilmezse tüm kaynaklarda aranır."
                    ),
                    "enum": [
                        "cv",
                        "mulakat_notlari",
                    ],
                },
            },
            "required": [
                "soru"
            ],
        },
    },
}

]


# =========================================================
# TOOL ÇALIŞTIRMA HARİTASI
# =========================================================

TOOL_FUNCTIONS = {
    "web_arama": tool_web_arama,
    "basvuru_ekle": tool_basvuru_ekle,
    "basvuru_ara": tool_basvuru_ara,
    "basvuru_listele": tool_basvuru_listele,
    "basvuru_guncelle": tool_basvuru_guncelle,
    "basvuru_istatistikleri": tool_basvuru_istatistikleri,
    "yaklasan_mulakatlari_getir": tool_yaklasan_mulakatlari_getir,
    "rag_ara": tool_rag_ara,
}


# =========================================================
# ARGUMENT DÜZELTME
# =========================================================

def _arguments_duzelt(fonksiyon, arguments):
    """
    LLM'in gönderdiği argument isimlerindeki küçük yazım
    hatalarını (ör. "posisyon" yerine "pozisyon") tolere eder.

    Küçük modeller bazen parametre adını neredeyse doğru ama
    birebir eşleşmeyen şekilde üretebiliyor. Bu durumda fonksiyon
    doğrudan TypeError ile patlıyor ve model çoğu zaman aynı
    hatayı tekrar üretip görevi tamamlayamıyor. Burada, tanınmayan
    bir anahtar fonksiyonun gerçek parametrelerinden biriyle
    yeterince yakınsa (difflib ile) o parametreye eşlenir;
    tanınmayan ve yeterince yakın bir eşleşmesi olmayan anahtarlar
    olduğu gibi bırakılır (böylece hâlâ anlaşılır bir hata verir).
    """

    gecerli_parametreler = set(
        inspect.signature(fonksiyon).parameters.keys()
    )

    duzeltilmis = {}

    for anahtar, deger in arguments.items():

        if anahtar in gecerli_parametreler:
            duzeltilmis[anahtar] = deger
            continue

        eslesme = get_close_matches(
            anahtar,
            gecerli_parametreler,
            n=1,
            cutoff=0.8,
        )

        duzeltilmis[eslesme[0] if eslesme else anahtar] = deger

    return duzeltilmis


# =========================================================
# TOOL ÇALIŞTIRICI
# =========================================================

def tool_calistir(tool_adi, arguments=None):
    """
    LLM tarafından talep edilen tool'u çalıştırır.

    Args:
        tool_adi (str): Çalıştırılacak tool'un adı.
        arguments (dict): Tool'a gönderilecek parametreler.

    Returns:
        dict: Tool sonucu.
    """

    if arguments is None:
        arguments = {}

    if tool_adi not in TOOL_FUNCTIONS:
        return {
            "basarili": False,
            "mesaj": f"Bilinmeyen tool: {tool_adi}",
        }

    fonksiyon = TOOL_FUNCTIONS[tool_adi]

    try:
        arguments = _arguments_duzelt(fonksiyon, arguments)

        sonuc = fonksiyon(**arguments)

        return sonuc

    except TypeError as hata:
        return {
            "basarili": False,
            "mesaj": (
                f"{tool_adi} aracına gönderilen "
                f"parametrelerde hata var: {str(hata)}"
            ),
        }

    except Exception as hata:
        return {
            "basarili": False,
            "mesaj": (
                f"{tool_adi} aracı çalıştırılırken "
                f"hata oluştu: {str(hata)}"
            ),
        }


# =========================================================
# MANUEL TEST
# =========================================================

if __name__ == "__main__":

    print("\n--- TOOL TESTİ ---\n")

    sonuc = tool_calistir(
        "basvuru_listele",
        {}
    )

    print(sonuc)