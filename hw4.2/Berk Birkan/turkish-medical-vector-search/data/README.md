# Data directories

- `raw/`: Hugging Face'ten indirilen değişmemiş kaynak Parquet dosyaları.
- `interim/`: Temizlenmiş ve deterministik olarak seçilmiş makaleler.
- `processed/`: Chunking ve embedding sonrasında üretilecek teslim verileri.
- `benchmark/`: Sürümlenecek kalibrasyon ve bağımsız test soruları.

`raw`, `interim` ve `processed` çalışma çıktıları Git'e eklenmez. Kaynak veri
gated olduğu için önce veri setinin Hugging Face sayfasındaki erişim koşulları
kabul edilmelidir.

```bash
python scripts/download_source.py
python scripts/select_articles.py
```

Seçim özeti `reports/metrics/selection_summary.json` altında sürümlenir; bu
dosya ham makale metni içermez.

