import sys
import logging
import numpy as np
import config
from ollama_embedder import OllamaEmbedder
from vector_db import LocalVectorDB

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_benchmark():
    print("=" * 75)
    print(" SIMILARITY THRESHOLD BENCHMARK & CALIBRATION TEST ")
    print("=" * 75)

    embedder = OllamaEmbedder()
    vector_db = LocalVectorDB()

    total_docs = vector_db.count()
    print(f"\n[+] Total Chunks in Vector DB: {total_docs}")

    if total_docs == 0:
        print("❌ Database empty! Please run 'python ingest.py' first.")
        return

    # 20 Relevant (Positive) Medical Queries
    relevant_queries = [
        "Diyabet hastalığının belirtileri ve tedavisi nedir?",
        "Glike hemoglobin HGB testi ne için yapılır?",
        "Hipoksemi kanda oksijen düşüklüğü belirtileri nelerdir?",
        "Bazofil BASO yüksekliği ve düşüklüğü ne anlama gelir?",
        "Endoskopik sleeve gastroplasti mide küçültme işlemi nasıl uygulanır?",
        "Sleeve gastrektomi ameliyatı kaç saat sürer?",
        "Açık kalp ameliyatı riskleri ve iyileşme süreci",
        "Sigara kullanımı ve stresin hipertansiyon üzerine etkileri",
        "Çocuklarda yüksek ateş durumunda yapılması gerekenler",
        "Çocuk acil servise hangi durumlarda başvurulmalıdır?",
        "Bebeklerde ve çocuklarda burun tıkanıklığı nasıl giderilir?",
        "Solunum sıkıntısı belirtileri ve tedavisi",
        "Ablasyon tedavisi nasıl yapılır ve kalbe etkileri",
        "Adenit lenf bezi iltihabı nedenleri ve belirtileri",
        "Kol ağrısı sebepleri ve hangi doktora gidilmeli?",
        "Kardiyovasküler hastalıkları önlemek için beslenme ve egzersiz",
        "Grip ve soğuk algınlığı arasındaki farklar ve tedavi",
        "Mide bulantısı neden olur ve diyabetik ketoasidoz ilişkisi",
        "Obezite tedavisinde cerrahi olmayan mide dikişleme yöntemi",
        "Çocuk göğüs hastalıkları ve hırıltılı solunum"
    ]

    # 10 Irrelevant (Negative) Non-Medical Queries
    irrelevant_queries = [
        "Siber güvenlik saldırılarından korunma yöntemleri nelerdir?",
        "Kripto para ve blokzincir teknolojisi nasıl çalışır?",
        "Araba motorunda yağ değişimi nasıl yapılır?",
        "Python yazılım dilinde döngüler ve fonksiyonlar",
        "Uzay seyahatleri ve Mars keşif araçları",
        "Evde lezzetli napoliten pizza tarifi nasıl hazırlanır?",
        "Futbolda 4-3-3 taktiği ve ofsayt kuralı nedir?",
        "Borsa İstanbul hisse senedi alım satım işlemleri",
        "Fotoğraf makinesinde diyafram ve enstantane ayarı",
        "İkinci el araba alırken dikkat edilmesi gereken ekspertiz noktaları"
    ]

    print(f"\n[1] Executing Relevant (Positive) Queries ({len(relevant_queries)} items)...")
    positive_scores = []
    for idx, q in enumerate(relevant_queries, 1):
        q_vec = embedder.get_embedding(q)
        results = vector_db.search(q_vec, top_k=1, similarity_threshold=None)
        score = results[0]["similarity_score"] if results else 0.0
        positive_scores.append(score)
        print(f"  • P{idx:02d}: '{q[:45]}...' -> Max Score: {score:.4f}")

    print(f"\n[2] Executing Irrelevant (Negative) Queries ({len(irrelevant_queries)} items)...")
    negative_scores = []
    for idx, q in enumerate(irrelevant_queries, 1):
        q_vec = embedder.get_embedding(q)
        results = vector_db.search(q_vec, top_k=1, similarity_threshold=None)
        score = results[0]["similarity_score"] if results else 0.0
        negative_scores.append(score)
        print(f"  • N{idx:02d}: '{q[:45]}...' -> Max Score: {score:.4f}")

    # Statistical Metrics
    pos_min = float(np.min(positive_scores))
    pos_max = float(np.max(positive_scores))
    pos_mean = float(np.mean(positive_scores))
    pos_median = float(np.median(positive_scores))

    neg_min = float(np.min(negative_scores))
    neg_max = float(np.max(negative_scores))
    neg_mean = float(np.mean(negative_scores))
    neg_median = float(np.median(negative_scores))

    print("\n" + "=" * 75)
    print(" STATISTICAL BENCHMARK SUMMARY ")
    print("=" * 75)
    print("📊 RELEVANT (POSITIVE) QUERY SCORES:")
    print(f"   - Minimum Score : {pos_min:.4f}")
    print(f"   - Maximum Score : {pos_max:.4f}")
    print(f"   - Mean Score    : {pos_mean:.4f}")
    print(f"   - Median Score  : {pos_median:.4f}")

    print("\n📊 IRRELEVANT (NEGATIVE) QUERY SCORES:")
    print(f"   - Minimum Score : {neg_min:.4f}")
    print(f"   - Maximum Score : {neg_max:.4f}")
    print(f"   - Mean Score    : {neg_mean:.4f}")
    print(f"   - Median Score  : {neg_median:.4f}")

    best_threshold = 0.48
    best_accuracy = -1.0
    best_fp = 999
    best_fn = 999

    print("\n" + "-" * 75)
    print(" THRESHOLD SIMULATION & OPTIMIZATION ")
    print("-" * 75)
    print(f"{'Threshold (T)':<14} | {'True Positives (TP)':<20} | {'False Positives (FP)':<20} | {'False Negatives (FN)':<20} | {'Accuracy':<12}")
    print("-" * 75)

    candidate_thresholds = np.arange(0.25, 0.65, 0.025)
    for t in candidate_thresholds:
        t = round(float(t), 4)
        tp = sum(1 for s in positive_scores if s >= t)
        fn = sum(1 for s in positive_scores if s < t)
        fp = sum(1 for s in negative_scores if s >= t)
        tn = sum(1 for s in negative_scores if s < t)

        total = len(positive_scores) + len(negative_scores)
        acc = (tp + tn) / total

        print(f"  {t:<12.3f} | {tp:<20} | {fp:<20} | {fn:<20} | %{acc*100:<10.1f}")

        if acc > best_accuracy or (acc == best_accuracy and fp < best_fp):
            best_accuracy = acc
            best_threshold = t
            best_fp = fp
            best_fn = fn

    print("=" * 75)
    print(f" 🏆 RECOMMENDED OPTIMAL THRESHOLD: {best_threshold:.3f}")
    print(f" • Accuracy                 : %{best_accuracy*100:.1f}")
    print(f" • False Positives (FP)     : {best_fp}")
    print(f" • False Negatives (FN)     : {best_fn}")
    print("=" * 75)

if __name__ == "__main__":
    run_benchmark()
