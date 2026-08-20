import json
import pandas as pd
import requests

# 1. AYARLAR
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mebi-gemma:latest"  # Ollama'daki model adı--> hf.co/unsloth/gemma-4-E2B-it-GGUF:Q4_0 ,mebi-gemma:latest--> bu fine-tune eilmiş model

# Gem'den aldığın JSON formatındaki veri seti dosyanın yolu
DATASET_PATH = "benchmark_dataset.json"

# 2. VERİ SETİNİ YÜKLE
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

results = []

print(f"🚀 Benchmark Başlatılıyor... Model: {MODEL_NAME}\n")

# 3. TEST DÖNGÜSÜ
for idx, item in enumerate(dataset, 1):
    # Prompt Hazırlığı (Sadece Soruyu ve A, B, C, D Şıklarını Veriyoruz)
    user_query = item["user_query"]
    context = item["context"]
    options = item["options"]

    prompt_text = f"""[DO NOT THINK] Direct Answer Only.

    Soru: {user_query}
    Bulunan İçerikler: {context}

    Aşağıdaki seçeneklerden hangisi MEBİ asistanının vermesi gereken EN DOĞRU cevaptır? Sadece doğru şıkkın harfini (A, B, C veya D) yaz.

    A) {options["A"]}
    B) {options["B"]}
    C) {options["C"]}
    D) {options["D"]}
    """

    # Sistem rolü ekleyerek modelin test formatına uymasını sağlıyoruz
    payload = {
        "model": MODEL_NAME,
        "system": "Sen bir test değerlendirme sistemisin. Yalnızca A, B, C veya D harfini döndür.",
        "prompt": prompt_text,
        "think": False,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 1024,  # Düşünme bloğunun kesilmemesi için token limitini artırdık
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response_data = response.json()
        model_output = response_data.get("response", "").strip()
    except Exception as e:
        model_output = f"HATA: {str(e)}"

    # Sonuçları listeye ekle
    results.append(
        {
            "ID": item["id"],
            "Kategori": item["category"],
            "Beklenen Cevap": item["correct_answer"],
            "Modelin Verdiği Yanıt (Ham Metin)": model_output,
        }
    )

    print(f"[{idx}/{len(dataset)}] Soru ID {item['id']} tamamlandı.")

# 4. TABLO OLUŞTURMA VE GÖSTERME
df = pd.DataFrame(results)

# Pandas gösterim ayarlarını genişlet (Metinler kesilmeden görünsün)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", 1000)

print("\n" + "=" * 80)
print("📊 BENCHMARK SONUÇ TABLOSU")
print("=" * 80)
print(df.to_string(index=False))

# 5. EXCEL / CSV OLARAK KAYDET
df.to_csv("benchmark_sonuclari_ham_model.csv", index=False, encoding="utf-8-sig")
print("\n✅ Tüm sonuçlar şeffaf bir şekilde 'benchmark_sonuclari_ham_model.csv' dosyasına kaydedildi.")

#%%

import json
import pandas as pd
import requests

# 1. AYARLAR
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mebi-gemma:latest"  # Fine-tune edilmiş modelin adı

DATASET_PATH = "benchmark_dataset.json"

# 2. VERİ SETİNİ YÜKLE
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

results = []

print(f"🚀 Fine-Tuned Benchmark Başlatılıyor... Model: {MODEL_NAME}\n")

# 3. TEST DÖNGÜSÜ
for idx, item in enumerate(dataset, 1):
    user_query = item["user_query"]
    context = item["context"]
    options = item["options"]

    prompt_text = f"""[DO NOT THINK] Direct Answer Only.

Soru: {user_query}
Bulunan İçerikler: {context}

Aşağıdaki seçeneklerden hangisi MEBİ asistanının vermesi gereken EN DOĞRU cevaptır? Sadece doğru şıkkın harfini (A, B, C veya D) yaz.

A) {options["A"]}
B) {options["B"]}
C) {options["C"]}
D) {options["D"]}
"""

    payload = {
        "model": MODEL_NAME,
        # Fine-tune modelin kendi davranış kalıbını ezmemek için
        # system rolünü yine değerlendirici olarak tutuyoruz.
        "system": "Sen bir test değerlendirme sistemisin. Yalnızca A, B, C veya D harfini döndür.",
        "prompt": prompt_text,
        "think": False,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 1024,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response_data = response.json()
        model_output = response_data.get("response", "").strip()
    except Exception as e:
        model_output = f"HATA: {str(e)}"

    results.append(
        {
            "ID": item["id"],
            "Kategori": item["category"],
            "Beklenen Cevap": item["correct_answer"],
            "Modelin Verdiği Yanıt (Ham Metin)": model_output,
        }
    )

    print(f"[{idx}/{len(dataset)}] Soru ID {item['id']} tamamlandı.")

# 4. TABLO VE CSV
df = pd.DataFrame(results)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", 1000)

print("\n" + "=" * 80)
print("📊 BENCHMARK SONUÇ TABLOSU (FINE-TUNED MODEL)")
print("=" * 80)
print(df.to_string(index=False))

df.to_csv("benchmark_sonuclari_finetuned_model.csv", index=False, encoding="utf-8-sig")
print("\n✅ Tüm sonuçlar 'benchmark_sonuclari_finetuned_model.csv' dosyasına kaydedildi.")

#%%
import pandas as pd

# 1. CSV DOSYALARINI YÜKLE
df_ham = pd.read_csv("benchmark_sonuclari_ham_model.csv")
df_ft = pd.read_csv("benchmark_sonuclari_finetuned_model.csv")

# 2. DOĞRULUK (ACCURACY) KONTROLÜ
df_ham["Ham_Dogru_Mu"] = (
    df_ham["Beklenen Cevap"].str.strip().str.upper()
    == df_ham["Modelin Verdiği Yanıt (Ham Metin)"].str.strip().str.upper()
)
df_ft["FT_Dogru_Mu"] = (
    df_ft["Beklenen Cevap"].str.strip().str.upper()
    == df_ft["Modelin Verdiği Yanıt (Ham Metin)"].str.strip().str.upper()
)

# 3. GENEL PERFORMANS HESAPLAMA
toplam_soru = len(df_ham)
ham_dogru = df_ham["Ham_Dogru_Mu"].sum()
ft_dogru = df_ft["FT_Dogru_Mu"].sum()

ham_acc = (ham_dogru / toplam_soru) * 100
ft_acc = (ft_dogru / toplam_soru) * 100
fark_acc = ft_acc - ham_acc

df_genel = pd.DataFrame(
    [
        {
            "Model": "Ham Model (Gemma-4-E2B)",
            "Toplam Soru": toplam_soru,
            "Doğru Sayısı": ham_dogru,
            "Başarı Oranı (%)": f"%{ham_acc:.2f}",
        },
        {
            "Model": "Fine-Tuned Model (MEBİ)",
            "Toplam Soru": toplam_soru,
            "Doğru Sayısı": ft_dogru,
            "Başarı Oranı (%)": f"%{ft_acc:.2f}",
        },
    ]
)

print("=" * 75)
print("📊 GENEL MODEL PERFORMANS KARŞILAŞTIRMASI")
print("=" * 75)
print(df_genel.to_string(index=False))
print(f"\n📈 Net İyileşme / Fark: %{fark_acc:+.2f}")

# 4. KATEGORİ BAZLI YÜZDESEL KARŞILAŞTIRMA
df_ham_kat = (
    df_ham.groupby("Kategori")["Ham_Dogru_Mu"]
    .agg(["count", "sum"])
    .reset_index()
)
df_ham_kat.columns = ["Kategori", "Toplam", "Ham_Dogru"]

df_ft_kat = (
    df_ft.groupby("Kategori")["FT_Dogru_Mu"].agg(["sum"]).reset_index()
)
df_ft_kat.columns = ["Kategori", "FT_Dogru"]

df_kat = pd.merge(df_ham_kat, df_ft_kat, on="Kategori")

# Yüzde Hesaplamaları
df_kat["Ham Başarı (%)"] = (
    (df_kat["Ham_Dogru"] / df_kat["Toplam"]) * 100
).round(2)
df_kat["FT Başarı (%)"] = (
    (df_kat["FT_Dogru"] / df_kat["Toplam"]) * 100
).round(2)
df_kat["Fark (%)"] = (df_kat["FT Başarı (%)"] - df_kat["Ham Başarı (%)"]).round(
    2
)

# Görsel Şıklık İçin Yüzde İmzası Ekleme
df_kat_gosterim = df_kat.copy()
df_kat_gosterim["Ham Başarı (%)"] = df_kat_gosterim["Ham Başarı (%)"].apply(
    lambda x: f"%{x:.2f}"
)
df_kat_gosterim["FT Başarı (%)"] = df_kat_gosterim["FT Başarı (%)"].apply(
    lambda x: f"%{x:.2f}"
)
df_kat_gosterim["Fark (%)"] = df_kat_gosterim["Fark (%)"].apply(
    lambda x: f"%{x:+.2f}"
)

print("\n" + "=" * 75)
print("🎯 KATEGORİ BAZLI YÜZDESEL KARŞILAŞTIRMA TABLOSU")
print("=" * 75)
print(df_kat_gosterim.to_string(index=False))

# 5. DETAYLI SORU KARŞILAŞTIRMA TABLOSU
df_detay = pd.DataFrame(
    {
        "ID": df_ham["ID"],
        "Kategori": df_ham["Kategori"],
        "Beklenen Cevap": df_ham["Beklenen Cevap"],
        "Ham Tahmin": df_ham["Modelin Verdiği Yanıt (Ham Metin)"],
        "Ham Durum": df_ham["Ham_Dogru_Mu"].map(
            {True: "✅ Doğru", False: "❌ Yanlış"}
        ),
        "FT Tahmin": df_ft["Modelin Verdiği Yanıt (Ham Metin)"],
        "FT Durum": df_ft["FT_Dogru_Mu"].map(
            {True: "✅ Doğru", False: "❌ Yanlış"}
        ),
    }
)

# 6. CSV OLARAK KAYDET
df_kat.to_csv(
    "kategori_bazli_yuzdesel_kiyaslama.csv", index=False, encoding="utf-8-sig"
)
df_detay.to_csv(
    "soru_bazli_detayli_kiyaslama.csv", index=False, encoding="utf-8-sig"
)

print("\n" + "=" * 75)
print(
    "✅ 'kategori_bazli_yuzdesel_kiyaslama.csv' ve 'soru_bazli_detayli_kiyaslama.csv' kaydedildi."
)


#%%

from datasets import load_dataset

# 1. JSON dosyanı yükle
dataset = load_dataset("json", data_files="benchmark_dataset.json")

# 2. Repo adını tam olarak görseldeki gibi yazıyoruz:
DATASET_REPO = "nypgd/gemma-benchmark-dataset"
HF_TOKEN = "" # Token'ını gir

# 3. Hub'a gönder (Bu işlem veriyi Parquet formatına çevirip Viewer'ı tetikler)
dataset.push_to_hub(DATASET_REPO, token=HF_TOKEN)

print("Yüklendi! Sayfayı yenileyebilirsin.")