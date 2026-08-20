"""
benchmark.py — 30 soruluk benchmark seti ile RAG sistemini değerlendirir.

Metrikler:
- Pozitif sorularda doğru retrieval oranı (top-k içinde cevap var mı)
- Negatif sorularda doğru red oranı (threshold altında mı)
- Genel doğruluk
- Threshold analizi (0.30-0.70 arası tarama)
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.retriever import Retriever

logger = logging.getLogger(__name__)

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.parent
BENCHMARK_PATH = PROJECT_ROOT / "data" / "benchmark.csv"


def load_benchmark(benchmark_path=None) -> List[Dict[str, str]]:
    """
    Benchmark CSV dosyasını yükler.

    Args:
        benchmark_path: CSV dosya yolu. None ise varsayılan kullanılır.

    Returns:
        List[Dict]: Her soru için {soru, tip, beklenen_url, beklenen_davranis}.
    """
    if benchmark_path is None:
        benchmark_path = BENCHMARK_PATH

    benchmark_path = Path(benchmark_path)
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark dosyası bulunamadı: {benchmark_path}")

    questions = []
    with open(benchmark_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(row)

    logger.info(f"Benchmark yüklendi: {len(questions)} soru")
    return questions


def evaluate_single_threshold(
    retriever: Retriever,
    questions: List[Dict[str, str]],
    threshold: float,
) -> Dict[str, Any]:
    """
    Tek bir threshold değeri ile tüm soruları değerlendirir.

    Args:
        retriever: Retriever instance.
        questions: Benchmark soruları.
        threshold: Test edilecek eşik değeri.

    Returns:
        Dict: Metrikler (positive_accuracy, negative_accuracy, overall_accuracy, vb.)
    """
    true_positives = 0   # Pozitif soru, doğru cevaplandı
    false_negatives = 0  # Pozitif soru, yanlışlıkla reddedildi
    true_negatives = 0   # Negatif soru, doğru reddedildi
    false_positives = 0  # Negatif soru, yanlışlıkla cevaplandı

    positive_count = 0
    negative_count = 0
    details = []

    for q in questions:
        soru = q["soru"]
        tip = q["tip"].strip().lower()
        beklenen = q["beklenen_davranis"].strip().lower()

        # Retrieval yap
        result = retriever.retrieve(soru, threshold=threshold)
        actual_status = result["status"]
        top_score = result["top_score"]

        if tip == "pozitif":
            positive_count += 1
            if actual_status == "found":
                true_positives += 1
                correct = True
            else:
                false_negatives += 1
                correct = False
        else:  # negatif
            negative_count += 1
            if actual_status == "rejected":
                true_negatives += 1
                correct = True
            else:
                false_positives += 1
                correct = False

        details.append({
            "soru": soru,
            "tip": tip,
            "beklenen": beklenen,
            "sonuc": actual_status,
            "top_score": top_score,
            "dogru": correct,
        })

    positive_accuracy = true_positives / positive_count if positive_count > 0 else 0
    negative_accuracy = true_negatives / negative_count if negative_count > 0 else 0
    total = positive_count + negative_count
    overall_accuracy = (true_positives + true_negatives) / total if total > 0 else 0

    # Precision ve recall hesapla
    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0
    )

    return {
        "threshold": threshold,
        "positive_accuracy": positive_accuracy,
        "negative_accuracy": negative_accuracy,
        "overall_accuracy": overall_accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "details": details,
    }


def threshold_sweep(
    retriever: Retriever,
    questions: List[Dict[str, str]],
    start: float = 0.30,
    end: float = 0.70,
    step: float = 0.05,
) -> List[Dict[str, Any]]:
    """
    Farklı threshold değerlerini tarayarak en iyisini bulur.

    Args:
        retriever: Retriever instance.
        questions: Benchmark soruları.
        start: Başlangıç eşik değeri.
        end: Bitiş eşik değeri.
        step: Adım büyüklüğü.

    Returns:
        List[Dict]: Her threshold için metrikler.
    """
    results = []
    threshold = start

    while threshold <= end + 0.001:
        logger.info(f"Threshold taranıyor: {threshold:.2f}")
        metrics = evaluate_single_threshold(retriever, questions, threshold)
        results.append(metrics)
        threshold += step
        threshold = round(threshold, 2)

    return results


def print_threshold_report(sweep_results: List[Dict[str, Any]]):
    """Threshold tarama sonuçlarını tablo olarak yazdırır."""

    print("\n" + "=" * 90)
    print("THRESHOLD ANALİZİ RAPORU")
    print("=" * 90)

    # Tablo başlığı
    header = (
        f"{'Threshold':>10} | {'Poz. Doğ.':>10} | {'Neg. Doğ.':>10} | "
        f"{'Genel':>8} | {'Precision':>10} | {'Recall':>8} | {'F1':>8}"
    )
    print(header)
    print("-" * 90)

    best_result = None
    best_f1 = -1

    for r in sweep_results:
        line = (
            f"{r['threshold']:>10.2f} | "
            f"{r['positive_accuracy']:>10.1%} | "
            f"{r['negative_accuracy']:>10.1%} | "
            f"{r['overall_accuracy']:>8.1%} | "
            f"{r['precision']:>10.3f} | "
            f"{r['recall']:>8.3f} | "
            f"{r['f1_score']:>8.3f}"
        )

        # En iyi F1 skorunu işaretle
        if r["f1_score"] > best_f1:
            best_f1 = r["f1_score"]
            best_result = r

        print(line)

    print("-" * 90)

    if best_result:
        print(f"\n🏆 En iyi threshold: {best_result['threshold']:.2f}")
        print(f"   F1 Score: {best_result['f1_score']:.3f}")
        print(f"   Genel Doğruluk: {best_result['overall_accuracy']:.1%}")
        print(f"   Pozitif Doğruluk: {best_result['positive_accuracy']:.1%}")
        print(f"   Negatif Doğruluk: {best_result['negative_accuracy']:.1%}")
        print(
            f"   TP={best_result['true_positives']}, "
            f"FN={best_result['false_negatives']}, "
            f"TN={best_result['true_negatives']}, "
            f"FP={best_result['false_positives']}"
        )

    return best_result


def run_benchmark(benchmark_path=None) -> Dict[str, Any]:
    """
    Tam benchmark sürecini çalıştırır: yükleme, threshold tarama, raporlama.

    Args:
        benchmark_path: Benchmark CSV dosya yolu.

    Returns:
        Dict: En iyi threshold değeri ve metrikleri.
    """
    print("\n" + "=" * 60)
    print("🏥 Türkçe Tıbbi RAG — Benchmark Değerlendirmesi")
    print("=" * 60)

    # 1. Benchmark sorularını yükle
    questions = load_benchmark(benchmark_path)
    print(f"\n📋 Yüklenen soru sayısı: {len(questions)}")

    positive_count = sum(1 for q in questions if q["tip"].strip().lower() == "pozitif")
    negative_count = sum(1 for q in questions if q["tip"].strip().lower() == "negatif")
    print(f"   Pozitif: {positive_count}, Negatif: {negative_count}")

    # 2. Retriever başlat
    retriever = Retriever(threshold=0.5)  # Threshold sweep'te override edilecek

    # 3. Threshold taraması
    print("\n🔍 Threshold taraması başlıyor (0.30 → 0.70, adım: 0.05)...")
    sweep_results = threshold_sweep(retriever, questions)

    # 4. Rapor yazdır
    best = print_threshold_report(sweep_results)

    # 5. En iyi threshold ile detaylı sonuçları göster
    if best:
        print(f"\n\n📊 En İyi Threshold ({best['threshold']:.2f}) — Detaylı Sonuçlar:")
        print("-" * 80)
        for detail in best["details"]:
            emoji = "✅" if detail["dogru"] else "❌"
            print(
                f"  {emoji} [{detail['tip']:>7}] "
                f"skor={detail['top_score']:.4f} → {detail['sonuc']:>8} | "
                f"{detail['soru'][:60]}"
            )

    return {
        "best_threshold": best["threshold"] if best else 0.55,
        "best_metrics": best,
        "all_results": sweep_results,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_benchmark()
