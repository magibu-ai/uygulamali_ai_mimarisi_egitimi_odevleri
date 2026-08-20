"""Modelin cagirabilecegi 5 arac.

Her arac sade bir Python fonksiyonudur ve METIN dondurur; bu metin modele geri
beslenir. Hicbiri hata firlatmaz — hata olursa Turkce bir aciklama doner, boylece
sohbet dongusu cokmez.

TOOL_SCHEMAS listesi ise modele "elinde su araclar var" demenin JSON halidir.

    web_search        -> guncel haber/analiz          (Tavily, yedek: DuckDuckGo)
    get_stock_price   -> hisse/kripto/endeks fiyati   (yfinance, anahtar gerekmez)
    get_exchange_rate -> doviz kuru                   (Frankfurter, anahtar gerekmez)
    calculate_return  -> kar-zarar hesabi             (yerelde, LLM matematik yapmasin)
    finance_concept   -> kavram aciklamasi            (yerel bilgi bankasi, RAG)
"""

import html
import logging
import re

import requests
import yfinance as yf

import config

# yfinance bulunamayan sembollerde stderr'e "possibly delisted / HTTP Error 404"
# gibi satirlar basar. Biz bu durumu zaten yakalayip Turkce mesaja ceviriyoruz;
# kutuphanenin gurultusu sohbet ekranini kirletmesin.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# chat/main tarafindan ayarlanabilir: bilgi bankasi aramasinda hangi embedding modeli.
ACTIVE_EMBED_KEY = config.EMBED_MODEL


# ─────────────────────────────────────────
# 1. WEB ARAMASI — Tavily, yedegi DuckDuckGo -> Wikipedia
# ─────────────────────────────────────────
#
# Neden kademeli? Tavily anahtari olmayan biri projeyi klonlayinca da calissin
# diye. Ucretsiz yedekler daha zayif ama asistani tamamen sessize almaktan iyidir.

# Tek baslarina anlamsiz sorgular. Model bazen kullanicinin cumlesinden sorgu
# kurmak yerine tetikleyici kelimeyi oldugu gibi yolluyor (olculdu: query='bugun'
# -> Tavily "bugun" kelimesinin sozluk anlamini getirdi). Bu durumda arama yapmak
# yerine modele DUZELTME talimati donmek hem hizli hem de ogretici.
STOP_QUERIES = {
    "bugun", "bugün", "haber", "haberler", "ne", "oldu", "ne oldu", "durum",
    "son durum", "gelismeler", "gelişmeler", "neden", "nedir", "piyasa", "borsa",
}


def web_search(query: str, max_results: int = 3) -> str:
    """Guncel haber, piyasa yorumu ve genel bilgi icin internette arama yapar."""
    query = (query or "").strip()
    if not query:
        return "Arama sorgusu bos. Aranacak konuyu anahtar kelimelerle yaz."
    if query.lower() in STOP_QUERIES:
        return (
            f"'{query}' tek basina arama sorgusu olamaz, anlamsiz sonuc doner. "
            "Hangi VARLIK ve hangi KONU hakkinda arama yapilacagini belirten "
            "bir sorguyla tekrar cagir. "
            "Ornek: 'BIST 100 bugun kapanis' veya 'ASELSAN hisse yukselis nedeni'."
        )

    if config.TAVILY_API_KEY:
        try:
            return _tavily_search(query, max_results)
        except (requests.RequestException, ValueError, KeyError) as exc:
            # Anahtar gecersiz/kota dolmus olabilir; sessizce ucretsiz yedege gec.
            print(f"  \033[90m   (Tavily kullanilamadi: {exc} — DuckDuckGo'ya geciliyor)\033[0m")

    return _duckduckgo_search(query, max_results)


def _tavily_search(query: str, max_results: int) -> str:
    """Tavily arama API'si. LLM'ler icin tasarlanmis: ozet + kaynak dondurur."""
    response = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
        json={
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": True,  # Tavily'nin kendi ozeti — kucuk modeller icin cok degerli
        },
        timeout=config.REQUEST_TIMEOUT,
    )
    if response.status_code == 401:
        raise ValueError("gecersiz TAVILY_API_KEY")
    if response.status_code == 432:
        raise ValueError("Tavily kotasi dolmus")
    response.raise_for_status()
    data = response.json()

    lines = [f"'{query}' icin guncel arama sonuclari (kaynak: Tavily):"]
    if data.get("answer"):
        lines.append(f"\nOZET: {data['answer']}")

    results = data.get("results") or []
    if not results and not data.get("answer"):
        return f"'{query}' icin sonuc bulunamadi."

    lines.append("\nKAYNAKLAR:")
    for i, item in enumerate(results, start=1):
        snippet = (item.get("content") or "").strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        published = item.get("published_date") or ""
        date_note = f" ({published[:10]})" if published else ""
        lines.append(f"{i}. {item.get('title', '-')}{date_note}\n   {snippet}\n   {item.get('url', '-')}")
    return "\n".join(lines)


def _duckduckgo_search(query: str, max_results: int) -> str:
    """Ucretsiz yedek: DuckDuckGo'nun sade (lite) arayuzunu kazir. Anahtar gerekmez."""
    try:
        response = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT,
        )
        # DDG'nin HTML'inde href, class'tan once gelir ve class tek tirnaklidir:
        #   <a rel="nofollow" href="https://..." class='result-link'>Baslik</a>
        pairs = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            response.text,
            flags=re.DOTALL,
        )
        results = []
        for url, raw_title in pairs[:max_results]:
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            if title:
                results.append(f"{len(results) + 1}. {title}\n   {html.unescape(url)}")
        if results:
            return f"'{query}' icin internet sonuclari (kaynak: DuckDuckGo):\n" + "\n".join(results)
    except requests.RequestException:
        pass  # asagidaki Wikipedia yedegine dus

    return _wikipedia_search(query, max_results)


def _wikipedia_search(query: str, max_results: int) -> str:
    """Son care: Turkce Wikipedia API'si. Guncel haber icin zayiftir, kavram icin iyidir."""
    try:
        data = requests.get(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search", "srsearch": query,
                "srlimit": max_results, "format": "json",
            },
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT,
        ).json()
        items = data.get("query", {}).get("search", [])
        if not items:
            return f"'{query}' icin sonuc bulunamadi."
        lines = []
        for i, item in enumerate(items, start=1):
            snippet = html.unescape(re.sub(r"<[^>]+>", "", item.get("snippet", "")))
            slug = item["title"].replace(" ", "_")
            lines.append(
                f"{i}. {item['title']}\n   {snippet}\n   https://tr.wikipedia.org/wiki/{slug}"
            )
        return f"'{query}' icin Wikipedia sonuclari:\n" + "\n".join(lines)
    except requests.RequestException as exc:
        return f"Arama yapilamadi: {exc}"


# ─────────────────────────────────────────
# 2. HISSE / KRIPTO / ENDEKS FIYATI — yfinance
# ─────────────────────────────────────────

# yfinance kripto varliklari "BTC-USD" bicimiyle tanir. Kullanici "BTC" yazarsa
# biz duzeltelim; modelin bunu her seferinde dogru bilmesini beklemeyelim.
CRYPTO_SYMBOLS = {
    "BTC", "ETH", "XRP", "SOL", "ADA", "DOGE", "AVAX", "DOT", "LTC", "BNB",
    "TRX", "MATIC", "SHIB", "LINK", "ATOM", "XLM", "UNI", "USDT", "USDC",
}


def _fmt(value) -> str:
    """Sayiyi buyuklugune gore uygun ondalikla yazar.

    Tek bir sabit ondalik ise yaramaz: 381.0000 TL sacma, 0.00 SHIB ise bilgisiz.
    Buyuk sayida 2, orta sayida 4, kucuk sayida 8 hane kullanip sondaki
    gereksiz sifirlari kirpiyoruz.
    """
    number = float(value)
    magnitude = abs(number)
    if magnitude >= 100:
        text = f"{number:,.2f}"
    elif magnitude >= 1:
        text = f"{number:,.4f}"
    else:
        text = f"{number:,.8f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _normalize_ticker(ticker: str) -> tuple[str, bool]:
    """Kullanicidan gelen kodu yfinance'in anladigi bicime cevirir.

    Doner: (sembol, kripto_mu)
    """
    symbol = ticker.strip().upper().replace(" ", "")
    base = symbol.split("-")[0]

    if base in CRYPTO_SYMBOLS:
        # BTC -> BTC-USD ; BTC-USD zaten dogru
        return (symbol if "-" in symbol else f"{symbol}-USD"), True
    if symbol.endswith("USD") and symbol[:-3] in CRYPTO_SYMBOLS:
        return f"{symbol[:-3]}-USD", True  # BTCUSD -> BTC-USD
    return symbol, False


def _read_quote(symbol: str) -> dict | None:
    """Bir sembol icin fiyat bilgisini toplar. Bulamazsa None doner.

    Uc kaynagi sirayla deneriz cunku hicbiri tek basina guvenilir degil:
      1. fast_info  -> hizli, ama bazen bos doner
      2. history()  -> en saglami, gecmis kapanislari da verir
      3. info       -> zengin (isim, para birimi) ama yavas ve sik rate-limit yer
    """
    stock = yf.Ticker(symbol)
    quote: dict = {}

    # 1. fast_info
    try:
        fast = stock.fast_info
        for key in ("lastPrice", "previousClose", "currency", "dayHigh", "dayLow", "lastVolume"):
            try:
                value = fast[key]
            except (KeyError, TypeError, AttributeError, IndexError):
                continue
            if value is not None:
                quote[key] = value
    except Exception:
        pass

    # 2. history — fiyat hala yoksa buradan al
    if not quote.get("lastPrice"):
        try:
            frame = stock.history(period="5d", auto_adjust=False)
            if not frame.empty:
                quote["lastPrice"] = float(frame["Close"].iloc[-1])
                if len(frame) > 1:
                    quote.setdefault("previousClose", float(frame["Close"].iloc[-2]))
                quote.setdefault("dayHigh", float(frame["High"].iloc[-1]))
                quote.setdefault("dayLow", float(frame["Low"].iloc[-1]))
                quote.setdefault("lastVolume", float(frame["Volume"].iloc[-1]))
                quote["asOf"] = str(frame.index[-1].date())
        except Exception:
            pass

    if not quote.get("lastPrice"):
        return None

    # 3. info — sadece isim/para birimi icin, basarisiz olursa onemli degil
    try:
        info = stock.info or {}
        quote.setdefault("currency", info.get("currency"))
        quote["name"] = info.get("shortName") or info.get("longName")
    except Exception:
        pass

    return quote


def get_stock_price(ticker: str) -> str:
    """Bir hisse senedi, endeks veya kripto paranin guncel/gecikmeli fiyatini getirir."""
    if not ticker or not ticker.strip():
        return "Ticker kodu bos. Ornek: THYAO.IS, AAPL, BTC-USD"

    symbol, is_crypto = _normalize_ticker(ticker)

    try:
        quote = _read_quote(symbol)

        # BIST hissesi ".IS" eki olmadan gelmis olabilir; bir kez de onu deneyelim.
        if quote is None and not is_crypto and "." not in symbol and "-" not in symbol:
            fallback = f"{symbol}.IS"
            quote = _read_quote(fallback)
            if quote is not None:
                symbol = fallback

        if quote is None:
            return (
                f"'{ticker}' icin fiyat bilgisi bulunamadi. Ticker kodunu kontrol edin. "
                "BIST icin '.IS' eki gerekir (THYAO.IS), kripto icin '-USD' (BTC-USD)."
            )

        price = float(quote["lastPrice"])
        currency = quote.get("currency") or ("USD" if is_crypto else "?")
        name = quote.get("name") or symbol

        lines = [f"{name} ({symbol}): {_fmt(price)} {currency}"]

        prev_close = quote.get("previousClose")
        if prev_close:
            prev_close = float(prev_close)
            change = price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0.0
            arrow = "📈" if change >= 0 else "📉"
            sign = "+" if change >= 0 else "-"
            lines.append(
                f"  {arrow} Onceki kapanisa gore: {sign}{_fmt(abs(change))} ({change_pct:+.2f}%)"
            )

        low, high = quote.get("dayLow"), quote.get("dayHigh")
        if low and high:
            lines.append(f"  Gunluk aralik: {_fmt(low)} - {_fmt(high)} {currency}")

        volume = quote.get("lastVolume")
        if volume:
            lines.append(f"  Hacim: {float(volume):,.0f}")

        if quote.get("asOf"):
            lines.append(f"  Veri tarihi: {quote['asOf']}")

        lines.append("  (Veri gecikmeli olabilir — kaynak: Yahoo Finance)")
        return "\n".join(lines)

    except Exception as exc:
        return f"Fiyat bilgisi alinamadi ({ticker}): {exc}"


# ─────────────────────────────────────────
# 3. DOVIZ KURU — Frankfurter (anahtar gerekmez)
# ─────────────────────────────────────────

def get_exchange_rate(base: str, target: str, amount: float = 1.0) -> str:
    """Iki para birimi arasindaki guncel kuru ve cevrilmis tutari getirir."""
    source = base.strip().upper()
    destination = target.strip().upper()

    # Frankfurter sadece itibari para birimlerini bilir. Kripto gelirse dogru araca yonlendir.
    if source in CRYPTO_SYMBOLS or destination in CRYPTO_SYMBOLS:
        return (
            f"{source}/{destination} bir kripto paritesi. Bunun icin get_stock_price aracini "
            f"'{(source if source in CRYPTO_SYMBOLS else destination)}-USD' ile cagirin."
        )

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 1.0

    try:
        data = requests.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": source, "symbols": destination},
            timeout=config.REQUEST_TIMEOUT,
        ).json()
        rate = (data.get("rates") or {}).get(destination)
        if rate is None:
            return (
                f"{source} -> {destination} kuru bulunamadi. Para birimi kodlarini kontrol edin "
                "(USD, EUR, TRY, GBP, JPY ...)."
            )
        return (
            f"1 {source} = {_fmt(rate)} {destination} ({data['date']} tarihli kur). "
            f"{_fmt(amount)} {source} = {_fmt(round(amount * rate, 2))} {destination}"
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        return f"Kur bilgisi alinamadi: {exc}"


# ─────────────────────────────────────────
# 4. GETIRI / KAR-ZARAR HESAPLAYICI (yerelde)
# ─────────────────────────────────────────
#
# Bu arac internete cikmaz. Var olma sebebi tek: dil modelleri aritmetikte
# guvenilmezdir. Hesabi Python yapar, model sadece sonucu aktarir.

def calculate_return(buy_price: float, sell_price: float, amount: float) -> str:
    """Alis fiyati, satis fiyati ve miktardan toplam getiri/kar-zarar hesaplar."""
    try:
        buy_price = float(buy_price)
        sell_price = float(sell_price)
        amount = float(amount)
    except (ValueError, TypeError):
        return "Hesaplama yapilamadi: alis fiyati, satis fiyati ve miktar sayi olmali."

    if buy_price <= 0:
        return "Hesaplama yapilamadi: alis fiyati sifirdan buyuk olmali."
    if amount <= 0:
        return "Hesaplama yapilamadi: miktar sifirdan buyuk olmali."

    total_buy = buy_price * amount
    total_sell = sell_price * amount
    profit = total_sell - total_buy
    profit_pct = (profit / total_buy) * 100
    label = "📈 KAR" if profit >= 0 else "📉 ZARAR"

    sign = "+" if profit >= 0 else "-"
    return (
        f"Alis : {_fmt(amount)} x {_fmt(buy_price)} = {total_buy:,.2f}\n"
        f"Satis: {_fmt(amount)} x {_fmt(sell_price)} = {total_sell:,.2f}\n"
        f"─────────────────────────\n"
        f"{label}: {sign}{abs(profit):,.2f} ({profit_pct:+.2f}%)\n"
        "(Komisyon, stopaj ve diger islem maliyetleri bu hesaba dahil degildir.)"
    )


# ─────────────────────────────────────────
# 5. FINANS KAVRAMI — yerel bilgi bankasi (RAG)
# ─────────────────────────────────────────

def finance_concept(question: str) -> str:
    """Finans kavramini SADECE indekslenmis bilgi bankasina dayanarak aciklar.

    Cevap burada bitmis haldedir; main.py'deki model bunu aynen aktarmalidir.
    """
    try:
        import finance_rag  # chromadb kurulu degilse asistanin geri kalani calissin
    except ImportError:
        return (
            "Bilgi bankasi kullanilamiyor: 'chromadb' kurulu degil. "
            "Kurmak icin: pip install -r requirements.txt"
        )

    try:
        result = finance_rag.answer_finance(question, embed_key=ACTIVE_EMBED_KEY)
    except RuntimeError as exc:
        return f"Bilgi bankasina ulasilamadi: {exc}"

    if not result["grounded"]:
        return (
            f"{result['answer']}\n"
            "(Bu konu yerel bilgi bankasinda yok — guncel bilgi icin web_search denenebilir.)"
        )

    sources = "\n".join(
        f"- {s['title']} — {s['source']} (benzerlik {s['similarity']})\n  {s['url']}"
        for s in result["sources"]
    )
    return f"{result['answer']}\n\nKaynaklar:\n{sources}"


# ─────────────────────────────────────────
# ARAC KAYIT TABLOSU
# ─────────────────────────────────────────

# Fonksiyon adi -> fonksiyon eslestirmesi (main.py bunu kullanir)
TOOLS = {
    "web_search": web_search,
    "get_stock_price": get_stock_price,
    "get_exchange_rate": get_exchange_rate,
    "calculate_return": calculate_return,
    "finance_concept": finance_concept,
}

# Modele "elinde su araclar var" demenin JSON hali.
# Aciklamalari kisa ve ayirt edici tutuyoruz: kucuk modeller uzun metinde bogulur
# ve iki aracin aciklamasi birbirine benzerse yanlis olani secer.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "Hisse senedi, endeks veya kripto paranin GUNCEL FIYATINI getirir. "
                "BIST hisseleri icin ticker sonuna '.IS' ekle (THYAO.IS, ASELS.IS). "
                "ABD hisseleri icin direkt kod (AAPL, MSFT). "
                "Kripto icin '-USD' ekle (BTC-USD, ETH-USD)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Varlik kodu. Ornek: THYAO.IS, AAPL, BTC-USD",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": (
                "Iki ITIBARI para birimi arasindaki guncel kuru ve cevrilmis tutari getirir. "
                "Ornek: USD/TRY, EUR/USD. Kripto icin KULLANMA, get_stock_price kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Kaynak para birimi kodu, ornegin USD",
                    },
                    "target": {
                        "type": "string",
                        "description": "Hedef para birimi kodu, ornegin TRY",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Cevrilecek tutar (varsayilan 1)",
                    },
                },
                "required": ["base", "target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                # DIKKAT: Buraya tetikleyici kelimeleri TIRNAK ICINDE yazmayin.
                # Onceki surumde "'bugun', 'ne oldu' ..." diye listelenmisti ve model
                # bu kelimeleri arama SORGUSU sandi: query='bugun' gonderdi.
                # Aciklama araci NE ZAMAN cagiracagini anlatmali, argumanin ne
                # olacagini degil — o is parametre aciklamasinin.
                "Guncel haber, piyasa gelismesi ve son durum bilgisi icin internette "
                "arama yapar. Bugun ne oldugu, bir fiyatin neden yukseldigi ya da "
                "dustugu, sirket haberleri gibi tarihe bagli sorularda bu araci cagir. "
                "Bu tur sorulari kendi bilginle cevaplama."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Arama motoruna gonderilecek anahtar kelimeler. Kullanicinin "
                            "cumlesini oldugu gibi kopyalama ve tek kelime gonderme; "
                            "varlik adini ve konuyu iceren kisa bir sorgu kur. "
                            "Iyi ornekler: BIST 100 bugun kapanis / ASELSAN hisse "
                            "yukselis nedeni / Bitcoin fiyat son durum"
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Sonuc sayisi (varsayilan 3)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_return",
            "description": (
                "Alis fiyati, satis fiyati ve miktar verilerek kar-zarar ve yuzde getiri "
                "hesaplar. Matematigi KENDIN YAPMA, her zaman bu araci cagir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "buy_price": {
                        "type": "number",
                        "description": "Birim alis fiyati",
                    },
                    "sell_price": {
                        "type": "number",
                        "description": "Birim satis fiyati",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Adet / miktar",
                    },
                },
                "required": ["buy_price", "sell_price", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finance_concept",
            "description": (
                "Finans KAVRAMLARINI yerel bilgi bankasindan aciklar: temettu, F/K orani, "
                "kaldirac, ETF, volatilite, stablecoin, aciga satis gibi. "
                "'... nedir', '... nasil hesaplanir', '... ne demek' sorulari icin kullan. "
                "Donen metni aynen aktar, uzerine kendi bilgini EKLEME."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Kullanicinin kavram sorusu",
                    },
                },
                "required": ["question"],
            },
        },
    },
]
