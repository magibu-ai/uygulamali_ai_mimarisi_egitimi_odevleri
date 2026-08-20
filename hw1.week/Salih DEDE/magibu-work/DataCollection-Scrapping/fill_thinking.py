import asyncio
import json
import os
import sys

import httpx

INPUT_DIR = "json_ciktilari"
OUTPUT_DIR = "json_ciktilari_with_thinking"
MERGED_OUTPUT_FILE = "trendyolProductAsistantQA.json"
ENV_FILE = ".env"
MAX_CONCURRENCY = 50

SYSTEM_PROMPT = (
    "Sen bir veri etiketleme asistanısın. Görevin, bir marangoz ürünü satıcısının "
    "müşteriye verdiği GERÇEK bir cevaptan yola çıkarak, satıcının o cevaba varmadan "
    "önce zihninden geçmiş olabilecek UZUN ve YAPILANDIRILMIŞ bir iç muhakeme "
    "(chain-of-thought) yazmaktır.\n"
    "Kurallar:\n"
    "- Muhakeme birinci ağızdan (satıcının kendi iç sesi gibi), Türkçe ve markdown "
    "formatında olmalı: numaralı adımlar, **kalın** alt başlıklar ve madde işaretleri "
    "kullan.\n"
    "- Verilen ürün özelliklerindeki somut detaylara (materyal, ölçü, ağırlık, "
    "garanti vb.) açıkça atıfta bulun ve bunları soruyla ilişkilendir.\n"
    "- Müşterinin sorusunu analiz et, ürün özelliklerine göre olası cevap "
    "alternatiflerini tart, gerekiyorsa bir alternatifi elediğini/düzelttiğini göster "
    "(kısa bir öz-eleştiri adımı), ve sonunda verilen GERÇEK cevaba nasıl vardığını "
    "netleştir.\n"
    "- Cevabın kendisini değiştirme veya birebir tekrar etme; sadece ona varan "
    "düşünce sürecini üret.\n"
    "- Sadece muhakeme metnini döndür, ekstra açıklama veya önsöz ekleme."
)


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def atomic_write_json(path, data):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


async def call_openrouter(client, base_url, api_key, model, urun_aciklamasi, soru, cevap, max_retries=3):
    user_prompt = (
        f"Ürün Özellikleri:\n{urun_aciklamasi}\n\n"
        f"Müşteri Sorusu: {soru}\n\n"
        f"Satıcının Verdiği Cevap: {cevap}\n\n"
        "Bu cevaba varmadan önceki iç muhakemeyi (thinking) yaz."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 1500,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            body = resp.json()
            return body["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            last_error = str(e)
        print(f"    Deneme {attempt}/{max_retries} başarısız: {last_error}")
        await asyncio.sleep(2 * attempt)

    raise RuntimeError(f"OpenRouter isteği başarısız oldu: {last_error}")


class MergedWriter:
    """Tüm ürünlerdeki tamamlanan diyalogları anlık olarak tek dosyada tutar."""

    def __init__(self, dosya_sirasi):
        self.dosya_sirasi = dosya_sirasi
        self.urun_sonuclari = {dosya_adi: [] for dosya_adi in dosya_sirasi}
        self.lock = asyncio.Lock()

    async def set_product_result(self, dosya_adi, diyaloglar):
        async with self.lock:
            self.urun_sonuclari[dosya_adi] = diyaloglar
            self._write_merged()

    def _write_merged(self):
        birlesik = []
        for dosya_adi in self.dosya_sirasi:
            birlesik.extend(self.urun_sonuclari[dosya_adi])
        atomic_write_json(MERGED_OUTPUT_FILE, birlesik)


async def process_product(client, base_url, api_key, model, sem, dosya_adi, diyaloglar, merged_writer, i, toplam):
    cikti_yolu = os.path.join(OUTPUT_DIR, dosya_adi)
    sonuc_slotlari = [None] * len(diyaloglar)
    tamamlanan = 0

    async def bir_diyalogu_isle(idx, diyalog):
        nonlocal tamamlanan
        system_msg = diyalog[0]
        user_msg = diyalog[1]
        assistant_msg = diyalog[2]
        urun_aciklamasi = system_msg["content"].split("Ürün Özellikleri:", 1)[-1].strip()

        async with sem:
            thinking = await call_openrouter(
                client, base_url, api_key, model,
                urun_aciklamasi, user_msg["content"], assistant_msg["content"],
            )

        assistant_msg["thinking"] = thinking
        sonuc_slotlari[idx] = [user_msg, assistant_msg]
        tamamlanan += 1

        tamamlanmis_sirali = [s for s in sonuc_slotlari if s is not None]
        atomic_write_json(cikti_yolu, tamamlanmis_sirali)
        await merged_writer.set_product_result(dosya_adi, tamamlanmis_sirali)
        print(f"  [{i}/{toplam}] {dosya_adi}: {tamamlanan}/{len(diyaloglar)} tamamlandı.")

    await asyncio.gather(*(bir_diyalogu_isle(idx, d) for idx, d in enumerate(diyaloglar)))


async def async_main():
    load_env_file(ENV_FILE)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("OPENROUTER_MODEL")

    if not api_key or not model:
        print("OPENROUTER_API_KEY ve OPENROUTER_MODEL ortam değişkenleri gerekli "
              "(bir .env dosyası ya da shell export ile sağlayabilirsin).")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    dosyalar = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".json"))
    print(f"{len(dosyalar)} adet dosya bulundu. Eşzamanlılık: {MAX_CONCURRENCY}\n")

    merged_writer = MergedWriter(dosyalar)
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async with httpx.AsyncClient() as client:
        for i, dosya_adi in enumerate(dosyalar, start=1):
            cikti_yolu = os.path.join(OUTPUT_DIR, dosya_adi)
            girdi_yolu = os.path.join(INPUT_DIR, dosya_adi)
            with open(girdi_yolu, "r", encoding="utf-8") as f:
                diyaloglar = json.load(f)

            if os.path.exists(cikti_yolu):
                with open(cikti_yolu, "r", encoding="utf-8") as f:
                    mevcut = json.load(f)
                if len(mevcut) >= len(diyaloglar):
                    print(f"[{i}/{len(dosyalar)}] {dosya_adi} zaten tamamlanmış, atlanıyor.")
                    await merged_writer.set_product_result(dosya_adi, mevcut)
                    continue

            print(f"[{i}/{len(dosyalar)}] {dosya_adi} işleniyor ({len(diyaloglar)} diyalog)...")
            await process_product(
                client, base_url, api_key, model, sem,
                dosya_adi, diyaloglar, merged_writer, i, len(dosyalar),
            )

    print(f"\nTüm dosyalar işlendi. Birleştirilmiş dosya: {MERGED_OUTPUT_FILE}")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
