"""
main.py — Türkçe Tıbbi RAG Sistemi ana çalıştırma scripti.

Adım adım pipeline:
1. load    — HF'den veri yükle + örnekle
2. chunk   — Makaleleri chunk'lara ayır
3. embed   — Chunk'ları vektörleştir
4. store   — ChromaDB'ye kaydet
5. benchmark — Benchmark çalıştır + threshold analizi
6. query   — Etkileşimli soru-cevap modu
7. export  — ChromaDB → HF Dataset export
8. all     — Tüm adımları sırasıyla çalıştır (1-4)
"""

import argparse
import logging
import json
import pickle
import sys
from pathlib import Path

from tqdm import tqdm

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"


def setup_logging(verbose=False):
    """Loglama ayarlarını yapar."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def step_load(args):
    """Adım 1: HF'den veri yükleme ve örnekleme."""
    from src.data_loader import load_hospital_data, save_raw_data

    print("\n" + "=" * 60)
    print("📥 ADIM 1: Veri Yükleme")
    print("=" * 60)

    splits = args.splits.split(",") if args.splits else None
    dataset = load_hospital_data(
        splits=splits,
        sample_size=args.sample_size,
    )

    print(f"\n✅ {len(dataset)} makale yüklendi.")
    print(f"   Kolonlar: {dataset.column_names}")
    print(f"   Örnek başlık: {dataset[0]['title']}")

    path = save_raw_data(dataset)
    print(f"   Kaydedildi: {path}")

    return dataset


def step_chunk(args):
    """Adım 2: Chunk'lama."""
    from src.data_loader import load_raw_data
    from src.chunking import chunk_dataset

    print("\n" + "=" * 60)
    print("✂️  ADIM 2: Chunking")
    print("=" * 60)

    dataset = load_raw_data()
    print(f"   {len(dataset)} makale yüklendi.")

    chunks = chunk_dataset(
        dataset,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print(f"\n✅ {len(chunks)} chunk oluşturuldu.")

    # Chunk'ları cache'le (embedding adımı için)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "chunks.pkl"
    with open(cache_path, "wb") as f:
        pickle.dump(chunks, f)
    print(f"   Cache kaydedildi: {cache_path}")

    return chunks


def step_embed(args):
    """Adım 3: Embedding üretimi."""
    from src.embedding import get_embedding_model
    import numpy as np

    print("\n" + "=" * 60)
    print("🔢 ADIM 3: Embedding")
    print("=" * 60)

    # Cache'den chunk'ları yükle
    cache_path = CACHE_DIR / "chunks.pkl"
    if not cache_path.exists():
        print("❌ Chunk cache bulunamadı. Önce 'chunk' adımını çalıştırın.")
        sys.exit(1)

    with open(cache_path, "rb") as f:
        chunks = pickle.load(f)
    print(f"   {len(chunks)} chunk cache'den yüklendi.")

    model = get_embedding_model()
    embeddings = model.encode_chunks(chunks, batch_size=args.batch_size)

    print(f"\n✅ Embedding tamamlandı. Shape: {embeddings.shape}")

    # Embedding'leri cache'le
    emb_cache_path = CACHE_DIR / "embeddings.npy"
    np.save(str(emb_cache_path), embeddings)
    print(f"   Cache kaydedildi: {emb_cache_path}")

    return embeddings


def step_store(args):
    """Adım 4: ChromaDB'ye kaydetme."""
    from src.vector_store import VectorStore
    import numpy as np

    print("\n" + "=" * 60)
    print("💾 ADIM 4: ChromaDB'ye Kaydetme")
    print("=" * 60)

    # Cache'den yükle
    chunks_cache = CACHE_DIR / "chunks.pkl"
    emb_cache = CACHE_DIR / "embeddings.npy"

    if not chunks_cache.exists() or not emb_cache.exists():
        print("❌ Cache dosyaları bulunamadı. Önce 'chunk' ve 'embed' adımlarını çalıştırın.")
        sys.exit(1)

    with open(chunks_cache, "rb") as f:
        chunks = pickle.load(f)

    embeddings = np.load(str(emb_cache))

    print(f"   {len(chunks)} chunk, {embeddings.shape} embedding yüklendi.")

    store = VectorStore()
    store.upsert_chunks(chunks, embeddings)

    stats = store.get_stats()
    print(f"\n✅ ChromaDB'ye kaydedildi.")
    print(f"   Koleksiyon: {stats['collection_name']}")
    print(f"   Toplam chunk: {stats['total_chunks']}")

    return store


def step_benchmark(args):
    """Adım 5: Benchmark çalıştırma."""
    from src.benchmark import run_benchmark

    print("\n" + "=" * 60)
    print("📊 ADIM 5: Benchmark")
    print("=" * 60)

    result = run_benchmark()

    print(f"\n✅ Benchmark tamamlandı.")
    print(f"   En iyi threshold: {result['best_threshold']:.2f}")

    return result


def step_query(args):
    """Adım 6: Etkileşimli soru-cevap modu."""
    print("⏳ Embedding modeli (magibu-200m) ve ChromaDB GPU'ya yükleniyor, lütfen bekleyin...", flush=True)
    from src.rag_pipeline import RAGPipeline, interactive_mode

    pipeline = RAGPipeline(
        threshold=args.threshold,
        top_k=args.top_k,
    )
    interactive_mode(pipeline)


def step_export(args):
    """Adım 7: HF Dataset export."""
    from export_to_hf import export_to_dataframe, export_to_parquet, push_to_hub

    print("\n" + "=" * 60)
    print("📤 ADIM 7: Export")
    print("=" * 60)

    df = export_to_dataframe()
    export_to_parquet(df)

    if args.hf_repo:
        push_to_hub(df, args.hf_repo)
    else:
        print("   HF push atlandı (--hf-repo belirtilmedi).")

    print(f"\n✅ Export tamamlandı. {len(df)} chunk export edildi.")


def step_all(args):
    """Tüm adımları sırasıyla çalıştırır (load → chunk → embed → store)."""
    print("\n" + "=" * 60)
    print("🚀 TÜM ADIMLAR ÇALIŞTIRILIYOR")
    print("=" * 60)

    step_load(args)
    step_chunk(args)
    step_embed(args)
    step_store(args)

    print("\n" + "=" * 60)
    print("✅ TÜM ADIMLAR TAMAMLANDI!")
    print("=" * 60)
    print("\nSonraki adımlar:")
    print("  python main.py --step benchmark   # Benchmark çalıştır")
    print("  python main.py --step query        # Soru-cevap modu")
    print("  python main.py --step export       # HF Dataset export")


def main():
    parser = argparse.ArgumentParser(
        description="Türkçe Tıbbi RAG Sistemi",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--step",
        type=str,
        default="all",
        choices=["load", "chunk", "embed", "store", "benchmark", "query", "export", "all"],
        help=(
            "Çalıştırılacak adım:\n"
            "  load      — HF'den veri yükle\n"
            "  chunk     — Chunk'lama\n"
            "  embed     — Embedding üretimi\n"
            "  store     — ChromaDB'ye kaydetme\n"
            "  benchmark — Benchmark + threshold analizi\n"
            "  query     — Etkileşimli soru-cevap\n"
            "  export    — HF Dataset export\n"
            "  all       — load → chunk → embed → store (varsayılan)"
        ),
    )

    # Veri yükleme parametreleri
    parser.add_argument("--splits", type=str, default=None, help="Hastane split'leri (virgülle ayrılmış, ör. 'acibadem,memorial')")
    parser.add_argument("--sample-size", type=int, default=500, help="Örneklenecek makale sayısı (varsayılan: 500)")

    # Chunking parametreleri
    parser.add_argument("--chunk-size", type=int, default=512, help="Chunk başına token sayısı (varsayılan: 512)")
    parser.add_argument("--chunk-overlap", type=int, default=64, help="Chunk örtüşme token sayısı (varsayılan: 64)")

    # Embedding parametreleri
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch boyutu (varsayılan: 64)")

    # Retrieval parametreleri
    parser.add_argument("--threshold", type=float, default=0.55, help="Benzerlik eşiği (varsayılan: 0.55)")
    parser.add_argument("--top-k", type=int, default=5, help="Top-k sonuç sayısı (varsayılan: 5)")

    # Export parametreleri
    parser.add_argument("--hf-repo", type=str, default=None, help="HF Dataset repo adı (ör. 'username/repo-name')")

    # Genel
    parser.add_argument("--verbose", action="store_true", help="Detaylı loglama")

    args = parser.parse_args()
    setup_logging(args.verbose)

    step_map = {
        "load": step_load,
        "chunk": step_chunk,
        "embed": step_embed,
        "store": step_store,
        "benchmark": step_benchmark,
        "query": step_query,
        "export": step_export,
        "all": step_all,
    }

    step_fn = step_map[args.step]
    step_fn(args)


if __name__ == "__main__":
    main()
