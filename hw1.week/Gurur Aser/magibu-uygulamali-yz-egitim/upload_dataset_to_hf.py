"""İthaki Bilimkurgu Klasikleri kataloğunu Hugging Face Hub'a dataset olarak yükler."""
from huggingface_hub import HfApi, login

HF_USERNAME = "gururaser"
REPO_ID = f"{HF_USERNAME}/ithaki-bilimkurgu-klasikleri"
CSV_PATH = "ithaki_bilimkurgu_klasikleri_ozetli.csv"
LISANS = "cc-by-nc-4.0"

README_ICERIK = f"""---
license: {LISANS}
language:
- tr
pretty_name: İthaki Bilimkurgu Klasikleri Kataloğu
tags:
- bilimkurgu
- kitap-katalogu
---

# İthaki Bilimkurgu Klasikleri Kataloğu

İthaki Yayın Grubu'nun "Bilimkurgu Klasikleri" serisindeki kitapların katalog
bilgilerini (yazar, çevirmen, yayınevi, sayfa sayısı, fiyat, özet vb.) içerir.
[ithakiyayingrubu.com](https://www.ithakiyayingrubu.com) üzerinden `ithaki_crawler.py`
ile toplanmıştır.

**Eğitim amaçlı oluşturulmuştur.** Bu veri seti dil modeli fine-tuning
çalışmaları için örnek kaynak olarak hazırlanmıştır; resmi bir katalog ya da
ticari bir ürün değildir. Fiyat ve stok bilgileri toplama anına aittir, güncel
olmayabilir. Telif hakları ilgili yayınevine/yazarlara aittir.

Hazırlayan, İthaki Bilim Kurgu serisinden 40'a yakın kitap okumuş bir okuyucudur.

## Sütunlar

| Sütun | Açıklama |
|---|---|
| kitap_adi | Kitabın Türkçe adı |
| yazar | Yazar |
| cevirmen | Çevirmen (varsa) |
| yayinevi | Yayınevi |
| kategori | Kategori |
| isbn | ISBN |
| kapak_tipi | Kapak tipi (varsa) |
| yayin_tarihi | Yayın tarihi (varsa) |
| olculeri | Kitap ölçüleri |
| orijinal_adi | Orijinal (özgün dil) adı (varsa) |
| sayfa_sayisi | Sayfa sayısı |
| indirim_orani | İndirim oranı |
| eski_fiyat | İndirim öncesi fiyat |
| satis_fiyati | Satış fiyatı |
| gorsel_url | Kapak görseli URL'si |
| ozet | Kitap özeti |
| kitap_url | Kaynak sayfa URL'si |

## Lisans

`{LISANS}` — Creative Commons Attribution-NonCommercial 4.0: ticari kullanım
yasaktır.
"""

login()  # write izinli HF token'ı ister

api = HfApi()
api.create_repo(repo_id=REPO_ID, repo_type="dataset", exist_ok=True)

api.upload_file(
    path_or_fileobj=CSV_PATH,
    path_in_repo=CSV_PATH,
    repo_id=REPO_ID,
    repo_type="dataset",
)

api.upload_file(
    path_or_fileobj=README_ICERIK.encode("utf-8"),
    path_in_repo="README.md",
    repo_id=REPO_ID,
    repo_type="dataset",
)

print(f"Yüklendi: https://huggingface.co/datasets/{REPO_ID}")
