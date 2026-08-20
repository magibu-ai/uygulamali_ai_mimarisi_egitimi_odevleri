import json
import os
import sys

from huggingface_hub import HfApi, create_repo

BENCHMARK_DOSYASI = "benchmark_coktan_secmeli.json"
DATASET_DIZINI = "hf_benchmark_dataset"
VERI_DOSYASI = os.path.join(DATASET_DIZINI, "data", "train.jsonl")
README_DOSYASI = os.path.join(DATASET_DIZINI, "README.md")
ENV_DOSYASI = "../Ders2/DataCollection-Scrapping/.env"

README_SABLONU = """---
language:
- tr
license: other
task_categories:
- question-answering
- multiple-choice
tags:
- e-ticaret
- musteri-hizmetleri
- turkce
- trendyol
- benchmark
pretty_name: Trendyol Marangoz Satıcı Asistanı Benchmark
size_categories:
- n<1K
---

# Trendyol Marangoz Satıcı Asistanı Benchmark

Bu veri kümesi, [SalihHub/trendyol-marangoz-urun-asistan-qa](https://huggingface.co/datasets/SalihHub/trendyol-marangoz-urun-asistan-qa)
ile aynı yöntemle ama **eğitim verisinde bulunmayan 6 farklı üründen** toplanan
alıcı sorusu / satıcı cevabı çiftlerinden türetilmiş, çoktan seçmeli bir
değerlendirme (benchmark) setidir. Fine-tune edilmiş satıcı asistanı modelini
ve diğer genel amaçlı modelleri aynı senaryo üzerinden karşılaştırmak için
hazırlanmıştır.

## İçerik

- **Toplam soru sayısı:** {n}
- **Sütunlar:**
  - `urun_id`: Kaynak Trendyol ürün kimliği.
  - `urun_aciklamasi`: Modelin bağlam olarak göreceği ürün özellikleri metni.
  - `kategori`: Sorunun konusu (malzeme, olcu, renk, aksesuar_parca, stok_varyant,
    kargo_lojistik, garanti, kurulum, diger).
  - `soru`: Alıcının sorusu (gerekiyorsa, ürün bilgisinde yer almayan bir bilgi
    alıcının zaten öğrenmiş/duymuş olduğu doğal bir cümleyle sorunun içine
    gömülmüştür; bkz. Üretim Süreci).
  - `soru_orijinal`: Bu gömme işleminden önceki, veri setindeki orijinal soru.
  - `secenekler`: `A`-`D` harfleriyle etiketlenmiş 4 şık.
  - `dogru_secenek`: Doğru şıkkın harfi.

## Şıkların tasarımı

Her soru için 4 şık, sadece doğru/yanlış bilgiyle değil **üslupla** da ayrışacak
şekilde tasarlandı:
- Doğru şık: gerçek veriyle tutarlı, kibar ve müşteriyi (bilgi olumsuz olsa bile)
  kırmadan/ilgisini canlı tutarak yanıtlayan bir cevap.
- Bir yanlış şık: aynı kibar üslupta ama gerçek bilgiyle çelişen yanlış bir cevap.
- Bir yanlış şık: doğru bilgiyi içeren ama kaba/soğuk, ikna çabası olmayan bir cevap.
- Bir yanlış şık: konuyla ilgisiz, veri setindeki gerçek kalıp/otomatik mesajlara
  benzer bir şablon cevap.

## Üretim süreci

1. Trendyol'un "Satıcıya Sor" bölümünden 6 üründen ham soru-cevap verisi
   Selenium ile toplandı (bkz. `Ders2/DataCollection-Scrapping/TrendyolScrapper.py`).
2. Ham veri, ürün başına tek bir LLM çağrısıyla analiz edilip şablon/otomatik
   cevaplar elenerek tutarlı bir soru havuzuna indirgendi
   (`Ders4/BenchmarkSoruHavuzuAnalizi.ipynb`).
3. Her soru, gerekiyorsa ürün bilgisinde yer almayan bilgiyi doğal bir cümleyle
   içine alacak şekilde genişletildi, ardından 1 doğru + 3 yanlış şık üretildi
   ve şıklar rastgele harflere dağıtıldı (`Ders4/CoktanSecmeliBenchmarkOlustur.ipynb`).

## Kullanım alanı ve sınırlamalar

- Bu veri kümesi eğitim/araştırma ve portföy amaçlıdır.
- Şıklar bir LLM tarafından üretildiği için nadiren hatalı/tutarsız olabilir.
- Veriler halka açık bir e-ticaret platformundan toplanmıştır; ticari kullanım
  öncesi ilgili platformun kullanım şartlarını gözden geçirmeniz önerilir.
"""


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def convert_to_jsonl():
    with open(BENCHMARK_DOSYASI, "r", encoding="utf-8") as f:
        sorular = json.load(f)

    os.makedirs(os.path.dirname(VERI_DOSYASI), exist_ok=True)
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        for soru in sorular:
            f.write(json.dumps(soru, ensure_ascii=False) + "\n")

    return len(sorular)


def write_readme(n):
    os.makedirs(DATASET_DIZINI, exist_ok=True)
    with open(README_DOSYASI, "w", encoding="utf-8") as f:
        f.write(README_SABLONU.format(n=n))


def main():
    load_env_file(ENV_DOSYASI)

    token = os.environ.get("HF_TOKEN")
    repo_id = os.environ.get("HF_BENCHMARK_REPO_ID")
    private = os.environ.get("HF_PRIVATE", "false").strip().lower() == "true"

    if not token or not repo_id:
        print("HF_TOKEN ve HF_BENCHMARK_REPO_ID ortam değişkenleri gerekli "
              "(Ders2/.env dosyasına HF_BENCHMARK_REPO_ID ekle).")
        sys.exit(1)

    if not os.path.exists(BENCHMARK_DOSYASI):
        print(f"{BENCHMARK_DOSYASI} bulunamadı. Önce CoktanSecmeliBenchmarkOlustur.ipynb çalıştırılmalı.")
        sys.exit(1)

    n = convert_to_jsonl()
    write_readme(n)

    create_repo(repo_id, repo_type="dataset", private=private, token=token, exist_ok=True)

    api = HfApi(token=token)
    api.upload_folder(
        repo_id=repo_id,
        folder_path=DATASET_DIZINI,
        repo_type="dataset",
        commit_message=f"{n} soruluk çoktan seçmeli benchmark yüklendi",
    )

    visibility = "private" if private else "public"
    print(f"Yüklendi: https://huggingface.co/datasets/{repo_id} ({visibility}, {n} soru)")


if __name__ == "__main__":
    main()
