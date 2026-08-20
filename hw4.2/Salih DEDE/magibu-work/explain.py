"""Retrieval adımlarını (dense/sparse skorlar, RRF füzyonu, seçilen parent'lar) eğitim amaçlı, açıklamalı şekilde terminale basan yardımcı fonksiyonlar."""


def _preview(text, n=70):
    text = text.replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def print_dense_results(query, rows):
    print(f"\n┌─ 1) DENSE ARAMA — kosinüs benzerliği (pgvector HNSW) ─────────")
    print(f"│  sorgu: \"{query}\"")
    print(f"│  skor = 1 − kosinüs_uzaklığı  →  1.0 birebir aynı anlam, 0.0 alakasız")
    print(f"├─────────────────────────────────────────────────────────────")
    for i, row in enumerate(rows, 1):
        print(f"│  {i:>2}. skor={row['score']:.4f}  {_preview(row['text'])}")
    print(f"└─────────────────────────────────────────────────────────────")


def print_sparse_results(query, rows):
    print(f"\n┌─ 2) SPARSE ARAMA — BM25 (ParadeDB tam metin indeksi) ─────────")
    print(f"│  sorgu: \"{query}\"")
    print(f"│  skor = kelime eşleşmesinin sıklık/nadirlik ağırlıklı BM25 puanı (üst sınırsız)")
    print(f"├─────────────────────────────────────────────────────────────")
    for i, row in enumerate(rows, 1):
        print(f"│  {i:>2}. skor={row['score']:.4f}  {_preview(row['text'])}")
    print(f"└─────────────────────────────────────────────────────────────")


def print_fusion_results(fused_rows, dense_rows, sparse_rows, k=60, top_n=10):
    dense_rank = {r["id"]: i + 1 for i, r in enumerate(dense_rows)}
    sparse_rank = {r["id"]: i + 1 for i, r in enumerate(sparse_rows)}
    print(f"\n┌─ 3) RRF FÜZYONU — dense + sparse sıralamalarının birleşimi ───")
    print(f"│  rrf_skoru = Σ 1/({k} + sıra)  →  iki listede de üst sıradaki chunk kazanır")
    print(f"├─────────────────────────────────────────────────────────────")
    for i, row in enumerate(fused_rows[:top_n], 1):
        dr = dense_rank.get(row["id"], "-")
        sr = sparse_rank.get(row["id"], "-")
        print(f"│  {i:>2}. dense#{dr!s:<3} sparse#{sr!s:<3}  {_preview(row['text'])}")
    print(f"└─────────────────────────────────────────────────────────────")


def print_selected_parents(blocks):
    print(f"\n┌─ 4) CHILD → PARENT GENİŞLETME — LLM'e verilecek bağlam ───────")
    for i, b in enumerate(blocks, 1):
        print(f"│  {i}. {b['title']}  ({b['source_url']})")
    print(f"└─────────────────────────────────────────────────────────────")


def print_attempt_header(attempt, max_attempts, query):
    print(f"\n════════════════ DENEME {attempt}/{max_attempts} ════════════════")
    print(f"  arama sorgusu: \"{query}\"")


def print_judge_verdict(result):
    if result.get("status") == "answered":
        print(f"\n✅ LLM YARGISI: bağlam yeterli, cevap üretildi.")
    else:
        next_q = result.get("reformulated_query")
        print(f"\n❌ LLM YARGISI: bağlam yetersiz (not_found).")
        if next_q:
            print(f"   → yeniden yazılan sorgu: \"{next_q}\"")


def print_final(outcome):
    print(f"\n════════════════ SONUÇ: {outcome['status'].upper()} ════════════════")
    print(f"{outcome['answer']}\n")


def print_confusion_matrix(counts, summary):
    tp, fp, tn, fn = counts["TP"], counts["FP"], counts["TN"], counts["FN"]
    print("\n┌─────────────────────────┬───────────────┬───────────────┐")
    print("│                         │ tahmin: cevap │ tahmin: ret   │")
    print("├─────────────────────────┼───────────────┼───────────────┤")
    print(f"│ gerçek: answerable      │  TP  {tp:>4}     │  FN  {fn:>4}     │")
    print(f"│ gerçek: unanswerable    │  FP  {fp:>4}     │  TN  {tn:>4}     │")
    print("└─────────────────────────┴───────────────┴───────────────┘")
    print(
        f"\n  precision {summary['precision']:.2f}   recall {summary['recall']:.2f}   "
        f"f1 {summary['f1']:.2f}   accuracy {summary['accuracy']:.2f}   "
        f"({summary['n_items']} soru)"
    )


def print_category_breakdown(results):
    by_category = {}
    for r in results:
        cat = r.get("category") or "-"
        stats = by_category.setdefault(cat, {"correct": 0, "total": 0})
        stats["total"] += 1
        if r["verdict"] in ("TP", "TN"):
            stats["correct"] += 1

    width = max(len(c) for c in by_category) if by_category else 10
    print(f"\n┌─ KATEGORİ KIRILIMI {'─' * max(0, width - 3)}┐")
    for cat in sorted(by_category):
        correct, total = by_category[cat]["correct"], by_category[cat]["total"]
        bar = "█" * correct + "░" * (total - correct)
        print(f"│  {cat:<{width}}  {correct:>2}/{total:<2}  {bar}")
    print("└" + "─" * (width + 16) + "┘")
