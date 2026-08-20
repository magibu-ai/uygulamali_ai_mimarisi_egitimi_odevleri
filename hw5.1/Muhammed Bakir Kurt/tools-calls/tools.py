"""
Finansal Veri Analisti Modeli için Araçlar (Tools).
Bu dosya modelin dış dünyadan döviz, kripto ve haber verilerini çekmesini sağlar.
"""

import html
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


# ---------------- 1. ARAÇ: KRİPTO PARA PERFORMANSI (YENİ) ----------------
def get_crypto_performance(coin_id: str) -> str:
    """CoinGecko API kullanarak kripto paranın güncel fiyatını ve 30 günlük getirisini çeker."""
    # API isimleri küçük harf bekler (örn: bitcoin, ethereum)
    coin = coin_id.strip().lower()
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": coin,
            "price_change_percentage": "30d"
        }
        response = requests.get(url, params=params, timeout=TIMEOUT).json()
        
        if not response:
            return f"'{coin}' adında bir varlık bulunamadı. Lütfen tam adını (örn: bitcoin) kullanın."
            
        data = response[0]
        price = data.get("current_price")
        change_24h = data.get("price_change_percentage_24h", 0)
        change_30d = data.get("price_change_percentage_30d_in_currency", 0)
        
        return (
            f"Varlık: {data['name']} ({data['symbol'].upper()})\n"
            f"Güncel Fiyat: ${price}\n"
            f"Son 24 Saatlik Değişim: %{change_24h:.2f}\n"
            f"Son 30 Günlük Kazanç/Kayıp: %{change_30d:.2f}"
        )
    except Exception as exc:
        return f"Kripto verisi alınamadı: {exc}"


# ---------------- 2. ARAÇ: DÖVİZ KURU ----------------
def get_exchange_rate(from_currency: str, to_currency: str, amount: float = 1.0) -> str:
    """Güncel döviz kurunu Frankfurter API'sinden getirir."""
    source = from_currency.strip().upper()
    target = to_currency.strip().upper()
    try:
        data = requests.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": source, "symbols": target},
            timeout=TIMEOUT,
        ).json()
        rate = data.get("rates", {}).get(target)
        if rate is None:
            return f"{source} -> {target} kuru bulunamadı."
        return (
            f"1 {source} = {rate} {target} ({data['date']} tarihli kur). "
            f"{amount} {source} = {round(float(amount) * rate, 2)} {target}"
        )
    except Exception as exc:
        return f"Kur bilgisi alınamadı: {exc}"


# ---------------- 3. ARAÇ: KRİPTO PARA PERFORMANSI (YENİ) ----------------
def get_donanimhaber_news(keyword: str = "") -> str:
    """
    DonanımHaber sitesini HTTP isteği ile çok hızlı bir şekilde tarar.
    Eğer keyword verilirse sadece o kelimeyi içeren haberleri getirir.
    """
    # Sitenin bizi bot sanıp engellememesi için standart bir tarayıcı kimliği (User-Agent) veriyoruz.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    if keyword:
        # Anahtar kelimeyi URL formatına çeviriyoruz (örn: "Yapay Zeka" -> "Yapay%20Zeka")
        guvenli_kelime = urllib.parse.quote(keyword)
        # Sitenin arama sayfasına yönlendiriyoruz
        url = f"https://www.donanimhaber.com/{guvenli_kelime}"
    else:
        # Keyword yoksa ana sayfaya git
        url = "https://www.donanimhaber.com/teknoloji-haberleri"

    try:
        # 1. Siteye doğrudan istek atıyoruz (Saniyeler içinde biter, tarayıcı açmaz)
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Eğer site 404, 500 gibi bir hata dönerse yakalar
        
        # 2. Gelen ham HTML'i parçalıyoruz
        soup = BeautifulSoup(response.text, "html.parser")

        # 3. Sizin belirlediğiniz o mükemmel rota!
        hedef_haberler = soup.select("div.dhkapsam div.tab-container ul li")

        baslik_metni = f"📰 DonanımHaber Son Gelişmeler (Arama: '{keyword}'):\n\n" if keyword else "📰 DonanımHaber Son Gelişmeler:\n\n"
        haberler = baslik_metni
        
        eklenen_haber_sayisi = 0

        for li in hedef_haberler:
            if eklenen_haber_sayisi >= 5: # En fazla 5 haber
                break
                
            aciklama_etiketi = li.find("div", class_="aciklama")
            aciklama = aciklama_etiketi.get_text(strip=True) if aciklama_etiketi else "Açıklama bulunamadı"

            baslik_etiketi = li.find(class_=lambda c: c and "baslik" in c and "history-add" in c)
            baslik = baslik_etiketi.get_text(strip=True) if baslik_etiketi else "Başlık bulunamadı"

            govde_etiketi = li.find("div", class_="govde")
            link_etiketi = govde_etiketi.find("a", href=True) if govde_etiketi else None
            
            if link_etiketi:
                haber_url = link_etiketi["href"]
                if haber_url.startswith("/"):
                    haber_url = "https://www.donanimhaber.com" + haber_url
            else:
                haber_url = "URL bulunamadı"

            # Şık Formatlama
            eklenen_haber_sayisi += 1
            haberler += f"{eklenen_haber_sayisi}. 📌 Başlık: {baslik}\n"
            haberler += f"   📝 Özet: {aciklama}\n"
            haberler += f"   🔗 Link: {haber_url}\n"
            haberler += "-" * 50 + "\n"

        if eklenen_haber_sayisi == 0:
            return f"'{keyword}' aramasıyla eşleşen güncel DonanımHaber sonucu bulunamadı."
        
        return haberler

    except Exception as exc:
        return f"Haberler çekilirken bir hata oluştu: {exc}"


# ---------------- ARAÇ SÖZLÜĞÜ VE JSON ŞEMALARI ----------------
TOOLS = {
    "get_donanimhaber_news": get_donanimhaber_news,
    "get_exchange_rate": get_exchange_rate,
    "get_crypto_performance": get_crypto_performance,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_donanimhaber_news",
            "description": "DonanımHaber teknoloji haber sitesinden en güncel teknoloji, oyun ve donanım haberlerini çeker. Eğer kullanıcı belirli bir konudaki haberleri istiyorsa (örn: yapay zeka, ekran kartı, telefon), keyword parametresini kullanarak filtreleme yapar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Haberlerde aranacak anahtar kelime (örn: 'Yapay Zeka', 'Apple', 'Oyun'). Eğer kullanıcı genel haberleri istiyorsa boş bırak."
                    }
                },
                "required": [] # Zorunlu değil, çünkü kullanıcı sadece "son haberleri ver" de diyebilir.
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "İki para birimi (USD, EUR, TRY vb.) arasındaki güncel kuru çevirmek için kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_currency": {"type": "string", "description": "Kaynak birim, örn: USD"},
                    "to_currency": {"type": "string", "description": "Hedef birim, örn: TRY"},
                    "amount": {"type": "number", "description": "Çevrilecek tutar"}
                },
                "required": ["from_currency", "to_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_performance",
            "description": "Kripto paraların (bitcoin, ethereum, solana vb.) güncel dolar fiyatını ve son 30 günlük getiri yüzdesini çekmek için kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {"type": "string", "description": "Kripto paranın tam İngilizce adı, örn: bitcoin, ethereum, ripple"}
                },
                "required": ["coin_id"],
            },
        },
    },
]