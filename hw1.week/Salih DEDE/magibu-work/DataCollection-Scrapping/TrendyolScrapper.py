import os
import re
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URUN_LISTESI_DOSYASI = "targetProductList.txt"
CIKTI_KLASORU = "json_ciktilari"

os.makedirs(CIKTI_KLASORU, exist_ok=True)

with open(URUN_LISTESI_DOSYASI, "r", encoding="utf-8") as f:
    urun_linkleri = [satir.strip() for satir in f if satir.strip()]

print(f"{len(urun_linkleri)} adet ürün linki bulundu.\n")

options = webdriver.ChromeOptions()
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument("window-size=1200,800")

driver = webdriver.Chrome(options=options)


def soru_cevap_url_olustur(url):
    urun_yolu, _, sorgu = url.partition("?")
    urun_id_eslesme = re.search(r"-p-(\d+)", urun_yolu)
    urun_id = urun_id_eslesme.group(1) if urun_id_eslesme else ""
    return f"{urun_yolu.rstrip('/')}/saticiya-sor?{sorgu}&qaContentId={urun_id}", urun_id


def urunu_isle(url):
    soru_cevap_url, urun_id = soru_cevap_url_olustur(url)

    # 1. Ürün sayfasından açıklamayı çek
    driver.get(url)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(2)

    urun_aciklamasi = "Açıklama bulunamadı."
    try:
        aciklama_elementi = driver.find_element(By.CLASS_NAME, "product-info-content")
        urun_aciklamasi = aciklama_elementi.text
    except:
        print("  Ürün açıklaması çekilemedi, sınıf (class) ismi değişmiş olabilir.")

    # 2. Soru-Cevap sayfasına geç
    driver.get(soru_cevap_url)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(2)

    # Soru-cevap listesi kendi iç scroll'unda "infinite scroll" ile yükleniyor.
    # Sayfayı değil, listedeki son kartı görünüme kaydırarak lazy-load'u tetikle.
    onceki_kart_sayisi = -1
    for _ in range(30):
        kartlar = driver.find_elements(By.CLASS_NAME, "question-answer-card")
        kart_sayisi = len(kartlar)
        if kart_sayisi == onceki_kart_sayisi:
            break
        onceki_kart_sayisi = kart_sayisi
        driver.execute_script("arguments[0].scrollIntoView({block: 'end'});", kartlar[-1])
        time.sleep(1.5)

    # 3. Soru-Cevap kartlarını yakala
    qa_kartlari = driver.find_elements(By.CLASS_NAME, "question-answer-card")
    print(f"  {len(qa_kartlari)} adet soru-cevap kartı bulundu.")

    tum_veriler = []
    for kart in qa_kartlari:
        try:
            soru = kart.find_element(By.CLASS_NAME, "question-answer-card-question-text").text
        except:
            continue
        if not soru:
            continue
        try:
            cevap = kart.find_element(By.CLASS_NAME, "seller-answer-content-text").text
        except:
            cevap = "Cevap yok"

        diyalog = [
            {
                "content": f"Sen bir marangoz ustasısın. Aşağıdaki ürünün satıcısısın.\nÜrün Özellikleri: {urun_aciklamasi}",
                "images": None,
                "role": "system",
                "thinking": None,
                "tool_calls": None
            },
            {
                "content": soru,
                "images": None,
                "role": "user",
                "thinking": None,
                "tool_calls": None
            },
            {
                "content": cevap,
                "images": None,
                "role": "assistant",
                "thinking": None,
                "tool_calls": None
            }
        ]
        tum_veriler.append(diyalog)

    return urun_id, tum_veriler


try:
    for i, url in enumerate(urun_linkleri, start=1):
        print(f"[{i}/{len(urun_linkleri)}] İşleniyor: {url}")

        onceden_bilinen_id = re.search(r"-p-(\d+)", url)
        onceden_bilinen_id = onceden_bilinen_id.group(1) if onceden_bilinen_id else None
        if onceden_bilinen_id and os.path.exists(os.path.join(CIKTI_KLASORU, f"{onceden_bilinen_id}.json")):
            print(f"  Zaten daha önce çekilmiş ({onceden_bilinen_id}.json), atlanıyor.\n")
            continue

        try:
            urun_id, tum_veriler = urunu_isle(url)
        except Exception as e:
            print(f"  Bu ürün işlenirken hata oluştu, atlanıyor: {e}\n")
            continue

        dosya_adi = f"{urun_id or i}.json"
        cikti_yolu = os.path.join(CIKTI_KLASORU, dosya_adi)
        with open(cikti_yolu, "w", encoding="utf-8") as f:
            json.dump(tum_veriler, f, ensure_ascii=False, indent=2)

        print(f"  Kaydedildi: {cikti_yolu} ({len(tum_veriler)} diyalog)\n")

    print("Tüm ürünler işlendi.")

finally:
    driver.quit()
