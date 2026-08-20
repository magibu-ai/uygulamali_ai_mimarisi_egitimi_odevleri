#!/usr/bin/env python3
"""Build the documented Colab/Jupyter assignment notebook deterministically."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "notebooks/turkish_medical_vector_search.ipynb"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.strip().splitlines(True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.strip().splitlines(True),
    }


CELLS = [
    markdown(
        """
# Türkçe Tıbbi Vektör Arama ve Threshold Analizi

Bu notebook, `umutertugrul/turkish-medical-articles` veri setinden 500
dermatoloji makalesi seçerek mixed chunking, yerel embedding, ChromaDB vektör
arama ve cevaplanabilirlik eşiği analizini baştan sona yeniden üretir.

Ana deney üretken LLM gerektirmez. En sondaki Qwen bölümü opsiyoneldir ve
varsayılan olarak kapalıdır.

> Eğitim amaçlıdır; tanı, tedavi veya kişiselleştirilmiş tıbbi öneri vermez.
"""
    ),
    markdown(
        """
## Deney tasarımı

1. Gated Hugging Face veri setini indir.
2. `Dermatoloji` branşını filtrele, kalite kontrollerinden geçir ve `seed=42`
   ile 500 makale seç.
3. Paragraf → cümle → token öncelikli 512 token + 64 overlap chunking uygula.
4. `magibu/embeddingmagibu-200m` ile 768 boyutlu L2-normalized vektör üret.
5. Vektörleri cosine ChromaDB koleksiyonunda sakla.
6. Ekstra 20 soruluk kalibrasyon setiyle threshold belirle.
7. Threshold'u değiştirmeden bağımsız 20 pozitif + 10 negatif soruda değerlendir.

Kalibrasyon/test ayrımı threshold'un test verisine aşırı uyumunu önler.
"""
    ),
    markdown(
        """
## 0. Ortam kurulumu

Notebook, repo kökünden veya `notebooks/` klasöründen açılabilir. Kurulum hücresi
önce gerçek proje kökünü bulur, sonra bağımlılıkları **bu notebook'un aktif
Python kernelına** kurar. Terminaldeki `pip` ile kernelın Python'u farklı
olabileceği için kurulum `sys.executable -m pip` üzerinden yapılır.

Proje Python 3.10+ gerektirir. VS Code'da sağ üstte görünen kernel daha eskiyse
önce Python 3.10 veya daha yeni bir kernel seçilmelidir. Colab'ın güncel Python
sürümü doğrudan desteklenir.
"""
    ),
    code(
        """
from pathlib import Path
import importlib
import subprocess
import sys

IN_COLAB = "google.colab" in sys.modules


def find_project_root(start: Path) -> Path:
    # Find the repository root from either the root or notebooks directory.
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src").is_dir():
            return candidate
    raise FileNotFoundError(
        "Proje kökü bulunamadı. Notebook'u klonlanmış "
        "turkish-medical-vector-search reposunun içinden açın."
    )


PROJECT_ROOT = find_project_root(Path.cwd())

if sys.version_info < (3, 10):
    raise RuntimeError(
        f"Bu proje Python 3.10+ gerektirir; aktif kernel {sys.version.split()[0]}. "
        "VS Code sağ üst menüsünden Python 3.10 veya daha yeni bir kernel seçin."
    )

# Varsayılan True: sürüm uyuşmazlıklarını da düzeltir; paketler güncelse pip no-op olur.
INSTALL_DEPENDENCIES = True

if INSTALL_DEPENDENCIES:
    print("Notebook bağımlılıkları aktif kernela kuruluyor:", sys.executable)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", f"{PROJECT_ROOT}[notebook]"],
        check=True,
    )
    importlib.invalidate_caches()
else:
    print("Gerekli bağımlılıklar aktif kernelda zaten kurulu.")

print("Python:", sys.executable)
print("Python sürümü:", sys.version.split()[0])
print("Proje kökü:", PROJECT_ROOT)
"""
    ),
    markdown(
        """
## 1. Yapılandırmayı yükleme

Tüm kritik kararlar `configs/default.yaml` içinde tutulur. Bilinmeyen alanlar
Pydantic tarafından reddedilir; böylece yazım hatalı bir config sessizce
çalışmaz.
"""
    ),
    code(
        """
src_path = str(PROJECT_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from turkish_medical_vector_search.config import load_config

config_path = PROJECT_ROOT / "configs" / "default.yaml"
assert config_path.is_file(), f"Config bulunamadı: {config_path}"
config = load_config(config_path)
print(config.model_dump_json(indent=2))
"""
    ),
    markdown(
        """
## 2. Hugging Face kimlik doğrulaması

Kaynak veri gated'dır. Önce veri seti sayfasındaki koşulları kabul edin. Token'ı
notebook hücresine yazmayın. Colab Secrets içindeki `HF_TOKEN`, standart Hugging
Face oturumu veya aşağıdaki güvenli `notebook_login()` arayüzü kullanılabilir.
"""
    ),
    code(
        """
from huggingface_hub import HfApi, notebook_login

try:
    account = HfApi().whoami()["name"]
    print("Hugging Face account:", account)
except Exception:
    print("Oturum bulunamadı. Açılan güvenli alana token girin.")
    notebook_login()
"""
    ),
    markdown(
        """
## 3. Kaynak veriyi indirme

Tam Parquet yaklaşık 107 MB'dir ve `data/raw/` altında tutulur. Ham veri Git'e
eklenmez. Hücre yeniden çalıştırıldığında Hugging Face cache kullanılır.
"""
    ),
    code(
        """
subprocess.run(
    [sys.executable, "scripts/download_source.py"],
    cwd=PROJECT_ROOT,
    check=True,
)
"""
    ),
    markdown(
        """
## 4. Dermatoloji makalelerini seçme

Zorunlu alanı eksik, 200 karakterden kısa, yinelenen URL/metin içeren kayıtlar
elenir. Kalan kayıtlar URL'ye göre sıralanıp `seed=42` ile örneklenir. Kaynak
satır sonları, sonraki mixed chunking aşaması için korunur.
"""
    ),
    code(
        """
subprocess.run([sys.executable, "scripts/select_articles.py"], cwd=PROJECT_ROOT, check=True)

import json
selection = json.loads(
    (PROJECT_ROOT / "reports/metrics/selection_summary.json").read_text(encoding="utf-8")
)
selection
"""
    ),
    markdown(
        """
## 5. Mixed chunking

Kısa paragraflar korunur. Uzun paragraflar önce cümle, gerekirse token sınırından
bölünür. Başlık her chunk'a eklenir ve 512 token bütçesine dahildir. 64 token
overlap, sınırdaki bağlam kaybını azaltır. Kısa son parçalar kontrollü overlap
genişletmesiyle en az 80 tokena tamamlanır.
"""
    ),
    code(
        """
subprocess.run([sys.executable, "scripts/chunk_articles.py"], cwd=PROJECT_ROOT, check=True)

chunking = json.loads(
    (PROJECT_ROOT / "reports/metrics/chunking_summary.json").read_text(encoding="utf-8")
)
chunking
"""
    ),
    code(
        """
import matplotlib.pyplot as plt
import pyarrow.parquet as pq

chunks = pq.read_table(PROJECT_ROOT / "data/processed/chunks.parquet")
token_counts = chunks.column("token_count").to_pylist()
plt.figure(figsize=(8, 4))
plt.hist(token_counts, bins=24, edgecolor="white")
plt.axvline(512, color="black", linestyle="--", label="512 token sınırı")
plt.xlabel("Token sayısı")
plt.ylabel("Chunk sayısı")
plt.title("Chunk token dağılımı")
plt.legend()
plt.show()
"""
    ),
    markdown(
        """
## 6. Yerel embedding üretimi

EmbeddingMagibu Türkçe odaklı, yaklaşık 200M parametreli, 8.192 token context ve
768 boyutlu bir modeldir. Dokümanlar `encode_document`, sorular `encode_query`
ile kodlanır. Çıktılar L2 normalize edilir. Batch checkpoint'leri kesintide
hesaplamayı korur.
"""
    ),
    code(
        """
subprocess.run([sys.executable, "scripts/embed_chunks.py"], cwd=PROJECT_ROOT, check=True)

embedding = json.loads(
    (PROJECT_ROOT / "reports/metrics/embedding_summary.json").read_text(encoding="utf-8")
)
embedding
"""
    ),
    code(
        """
embedded = pq.read_table(PROJECT_ROOT / "data/processed/chunks_with_vectors.parquet")
print(embedded.schema)
assert embedded.num_rows == 1019
assert len(embedded.column("chunk_vector")[0].as_py()) == 768
"""
    ),
    markdown(
        """
## 7. ChromaDB cosine koleksiyonu

Chroma cosine distance döndürür. Bu projede kullanıcıya gösterilen ve threshold
ile karşılaştırılan değer `cosine_similarity = 1 - distance` formülüyle elde
edilir.
"""
    ),
    code(
        """
subprocess.run([sys.executable, "scripts/build_chroma.py"], cwd=PROJECT_ROOT, check=True)
"""
    ),
    markdown("## 8. Örnek semantic search"),
    code(
        """
import chromadb

from turkish_medical_vector_search.embeddings.local import LocalSentenceEmbedder
from turkish_medical_vector_search.retrieval.search import search_collection

question = "Cildimizi kışa hazırlamak için neler yapmalıyız?"
embedder = LocalSentenceEmbedder(
    config.embedding.model_id,
    expected_dimension=config.embedding.dimension,
    normalize=config.embedding.normalize,
)
query_vector = embedder.encode_queries([question])[0].tolist()
client = chromadb.PersistentClient(
    path=str(PROJECT_ROOT / config.vector_store.persist_directory)
)
collection = client.get_collection(config.vector_store.collection_name)
result = search_collection(
    collection,
    question=question,
    query_vector=query_vector,
    top_k=3,
    threshold=config.retrieval.threshold,
    abstention_message=config.retrieval.abstention_message,
)

print("Answerable:", result.answerable)
print(result.message or "Threshold geçildi.")
for rank, hit in enumerate(result.hits, start=1):
    print(f"#{rank} similarity={hit.similarity:.4f} | {hit.metadata['title']}")
    print(hit.metadata["url"])
"""
    ),
    markdown(
        """
## 9. Benchmark hazırlama

Pozitif sorular elle doğrulanmış evidence chunk ve URL içerir. Negatif soruların
ayırt edici terimleri corpus'un tamamında sıfır geçişle doğrulanır. Kalibrasyon
20, bağımsız test 30 sorudur.
"""
    ),
    code(
        """
subprocess.run([sys.executable, "scripts/prepare_benchmark.py"], cwd=PROJECT_ROOT, check=True)

validation = json.loads(
    (PROJECT_ROOT / "reports/metrics/benchmark_validation.json").read_text(encoding="utf-8")
)
validation
"""
    ),
    markdown(
        """
## 10. Threshold kalibrasyonu ve bağımsız test

Yanlış kabul maliyeti 2, yanlış ret maliyeti 1 alınır. Threshold yalnızca
kalibrasyondan seçilir. Test sonuçları threshold dondurulduktan sonra hesaplanır.
"""
    ),
    code(
        """
subprocess.run([sys.executable, "scripts/evaluate_benchmark.py"], cwd=PROJECT_ROOT, check=True)

evaluation = json.loads(
    (PROJECT_ROOT / "reports/metrics/threshold_evaluation.json").read_text(encoding="utf-8")
)
evaluation
"""
    ),
    code(
        """
import csv

threshold = evaluation["threshold_selection"]["selected_threshold"]
calibration_rows = [
    json.loads(line)
    for line in (PROJECT_ROOT / "reports/metrics/calibration_results.jsonl").read_text().splitlines()
]
test_rows = [
    json.loads(line)
    for line in (PROJECT_ROOT / "reports/metrics/test_results.jsonl").read_text().splitlines()
]

fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for axis, rows, title in zip(axes, [calibration_rows, test_rows], ["Kalibrasyon", "Test"]):
    pos = [row["top_similarity"] for row in rows if row["is_answerable"]]
    neg = [row["top_similarity"] for row in rows if not row["is_answerable"]]
    axis.scatter(pos, [1] * len(pos), label="Pozitif")
    axis.scatter(neg, [0] * len(neg), label="Negatif")
    axis.axvline(threshold, color="black", linestyle="--", label=f"Eşik={threshold:.4f}")
    axis.set_title(title)
    axis.set_xlabel("Top-1 cosine similarity")
    axis.set_yticks([0, 1], ["Negatif", "Pozitif"])
axes[0].legend()
plt.show()
"""
    ),
    markdown(
        """
## 11. Sonuçların yorumu

Bağımsız testte answerability precision 1,00, recall 0,95 ve F1 0,9744'tür.
Exact chunk Recall@1 ve parent Recall@1 0,50'dir. Bazı sorularda aynı bilgiyi
taşıyan alternatif makalelerin beklenen kanıtın önüne geçmesi bu farkı açıklar.
Bu nedenle threshold başarısı, exact evidence ranking başarısıyla
karıştırılmamalıdır.
"""
    ),
    markdown(
        """
## 12. Hugging Face Dataset dışa aktarma

Yükleme varsayılan olarak kapalıdır. Repo kimliğini kendinize göre ayarlayıp
yalnızca açık onayla çalıştırın. Hugging Face tokenı koda yazılmaz.
"""
    ),
    code(
        """
PUSH_TO_HUB = False
HF_DATASET_REPO = "berkbirkan/turkish-dermatology-rag-dataset"

subprocess.run([sys.executable, "scripts/export_hf_dataset.py"], cwd=PROJECT_ROOT, check=True)

if PUSH_TO_HUB:
    from datasets import Dataset
    dataset = Dataset.from_parquet(PROJECT_ROOT / "hf_dataset/data/train.parquet")
    dataset.push_to_hub(HF_DATASET_REPO)
else:
    print("Yerel HF paketi doğrulandı; PUSH_TO_HUB=False olduğu için yüklenmedi.")
"""
    ),
    markdown(
        """
## 13. Opsiyonel yerel Qwen RAG

Bu bölüm ana ödevden bağımsızdır. Varsayılan `False` olduğu için model indirilmez
ve GPU belleği kullanılmaz. Threshold geçilmezse LLM hiçbir durumda çağrılmaz.

EmbeddingMagibu ile Qwen'in aynı boyutta olması gerekmez: embedding modeli
sorgu ve chunk'ları 768 boyutlu arama vektörlerine dönüştürür; Qwen ise threshold'u
geçen chunk metinlerini okur. 4-bit çalıştırma için ücretsiz Colab T4 GPU
önerilir. Önce `pip install -e ".[llm]"` komutunu çalıştırın.
"""
    ),
    code(
        """
RUN_OPTIONAL_LOCAL_LLM = False

if RUN_OPTIONAL_LOCAL_LLM:
    from turkish_medical_vector_search.generation import LocalQwenGenerator, answer_from_search

    # `result`, 8. bölümde threshold uygulanarak elde edilen SearchResult nesnesidir.
    generator = LocalQwenGenerator(
        model_id=config.optional_llm.model_id,
        load_in_4bit=config.optional_llm.load_in_4bit,
        max_new_tokens=config.optional_llm.max_new_tokens,
    )
    generated = answer_from_search(result, generator, max_context_chunks=3)
    print(generated.text)
    for source in generated.sources:
        print(f"[{source['index']}] {source['title']} - {source['url']}")
else:
    print("Opsiyonel yerel LLM kapalı; model indirilmedi.")
"""
    ),
    markdown(
        """
## 14. Sınırlılıklar ve kapanış

- Kaynaklar klinik kılavuz değil, halka açık sağlık makaleleridir.
- 500 makale ve 50 soru tüm dermatolojiyi temsil etmez.
- Veri veya embedding modeli değişirse threshold yeniden kalibre edilmelidir.
- Sistem tıbbi karar desteği olarak kullanılmamalıdır.
- Kaynak URL ve kanıt chunk'ı her kabul edilen sonuçla gösterilmelidir.

Bu notebook'un zorunlu çıktısı; veriyi chunk'lara ayıran, 768 boyutlu vektörleri
saklayan, cosine arama yapan ve düşük güvenli sorularda kesin olarak cevap vermeyen
yeniden üretilebilir bir bilgi erişim sistemidir.
"""
    ),
]


def main() -> None:
    notebook = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.10"},
            "colab": {"name": OUTPUT.name, "provenance": []},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(CELLS)} cells to {OUTPUT}")


if __name__ == "__main__":
    main()
