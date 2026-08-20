import asyncio
import csv
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_URL = "https://www.ithakiyayingrubu.com"
START_URL = "https://www.ithakiyayingrubu.com/bilimkurgu-klasikleri?PageNumber=5&PageSize=24"
OUTPUT_CSV = "ithaki_bilimkurgu_klasikleri_p5.csv"
DELAY_BETWEEN_PAGES = 3.0

CSV_FIELDS = [
    "kitap_adi", "yazar", "cevirmen", "yayinevi", "kategori", "isbn",
    "kapak_tipi", "yayin_tarihi", "olculeri", "orijinal_adi",
    "sayfa_sayisi", "indirim_orani", "eski_fiyat", "satis_fiyati",
    "gorsel_url", "ozet", "kitap_url"
]

SPEC_SELECTORS = {
    "isbn": "li.gtin span.value",
    "kategori": "li.productfeatures-category .value",
    "yayinevi": "li.productfeatures-manufacturer .value",
    "sayfa_sayisi": "li#Specificationsayfasayisi .value",
    "olculeri": "li#Specificationolculeri .value",
    "yayin_tarihi": "li#Specificationcikistarihi .value",
    "yazar": "li#Specificationyazar .value",
    "cevirmen": "li#Specificationcevirmen .value",
    "kapak_tipi": "li#Specificationkapaktipi .value",
    "orijinal_adi": "li#Specificationorijinaladi .value"
}


async def fetch_book_links(crawler: AsyncWebCrawler, catalog_url: str) -> List[str]:
    logging.info(f"Kategori sayfası taranıyor: {catalog_url}")
    try:
        config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for="css:div.products-list__item")
        result = await crawler.arun(url=catalog_url, config=config)
        
        if not result.success:
            logging.error(f"Kategori sayfası çekilemedi: {result.error_message}")
            return []

        soup = BeautifulSoup(result.html, "html.parser")
        links = list(dict.fromkeys(
            urljoin(BASE_URL, a["href"])
            for a in soup.select("div.products-list__item a.product-info-detail")
            if a.get("href")
        ))
        logging.info(f"Toplam {len(links)} adet kitap linki bulundu.")
        return links
    except Exception as e:
        logging.error(f"Kategori sayfası taranırken hata oluştu [{catalog_url}]: {e}")
        return []


async def parse_book_detail(crawler: AsyncWebCrawler, book_url: str) -> Dict[str, Any]:
    logging.info(f"Kitap detay sayfası taranıyor: {book_url}")
    data = {field: "" for field in CSV_FIELDS}
    data["kitap_url"] = book_url

    try:
        config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, delay_before_return_html=1.0)
        result = await crawler.arun(url=book_url, config=config)
        
        if not result.success:
            logging.error(f"Kitap detay sayfası çekilemedi [{book_url}]: {result.error_message}")
            return data

        soup = BeautifulSoup(result.html, "html.parser")

        def text_of(selector: str) -> str:
            el = soup.select_one(selector)
            return el.get_text(strip=True) if el else ""

        # 1. Başlık ve Özellikler
        data["kitap_adi"] = text_of("h1.product__name")
        for key, selector in SPEC_SELECTORS.items():
            data[key] = text_of(selector)

        # 2. Fiyatlar ve İndirim
        discount_el = soup.select_one("div.product-card__badge--sale")
        if discount_el:
            data["indirim_orani"] = discount_el.get_text(" ", strip=True).replace("indirim", "").strip()

        data["eski_fiyat"] = text_of("div.product__old-price")
        data["satis_fiyati"] = text_of("div.product__new-price")

        # 3. Görsel Linki
        img_el = soup.select_one(".product-gallery__carousel-item img")
        if img_el:
            img_src = img_el.get("data-fullsize") or img_el.get("data-full") or img_el.get("src")
            data["gorsel_url"] = urljoin(BASE_URL, img_src) if img_src else ""

        # 4. Özet / Tanıtım Metni
        # Telif hakkına girebileceği sebebi ile yorum satırına alınmıştır:
        # summary_el = soup.select_one("div.product-details-preview")
        # data["ozet"] = summary_el.get_text(" ", strip=True) if summary_el else ""

    except Exception as e:
        logging.error(f"Kitap detay sayfası işlenirken beklenmeyen hata [{book_url}]: {e}")

    return data


async def main():
    print("=== Crawl4AI İthaki Yayın Grubu Kitap Crawler ===")
    async with AsyncWebCrawler(verbose=True) as crawler:
        book_links = await fetch_book_links(crawler, START_URL)
        if not book_links:
            print("Kitap linki bulunamadı.")
            return

        # CSV dosyasını baştan oluşturup başlıkları yazalım
        with open(OUTPUT_CSV, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            f.flush()

        for index, link in enumerate(book_links, start=1):
            print(f"[{index}/{len(book_links)}] İşleniyor: {link}")
            book_data = await parse_book_detail(crawler, link)
            
            # Her kitap verisi çekildiği anda CSV dosyasına eklenir
            with open(OUTPUT_CSV, mode="a", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerow(book_data)
                f.flush()

            await asyncio.sleep(DELAY_BETWEEN_PAGES)

    print(f"\nTarama tamamlandı! Tüm veriler '{OUTPUT_CSV}' dosyasına aktarıldı.")


if __name__ == "__main__":
    asyncio.run(main())
