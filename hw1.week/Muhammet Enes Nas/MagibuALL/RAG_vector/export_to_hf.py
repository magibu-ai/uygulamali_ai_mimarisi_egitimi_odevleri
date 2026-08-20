"""
export_to_hf.py — ChromaDB koleksiyonunu Hugging Face Dataset olarak export eder.

Zorunlu kolonlar: url, chunk_text, chunk_vector
Ek metadata kolonları: title, source, parent_id
"""

import os
import logging
from pathlib import Path

import pandas as pd
from datasets import Dataset
from dotenv import load_dotenv

from src.vector_store import VectorStore

load_dotenv()

logger = logging.getLogger(__name__)

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent


def export_to_dataframe(vector_store: VectorStore = None) -> pd.DataFrame:
    """
    ChromaDB koleksiyonundan tüm verileri pandas DataFrame'e dönüştürür.

    Args:
        vector_store: VectorStore instance. None ise yeni oluşturulur.

    Returns:
        pd.DataFrame: url, chunk_text, chunk_vector ve metadata kolonları.
    """
    if vector_store is None:
        vector_store = VectorStore()

    logger.info("ChromaDB'den veriler çekiliyor...")
    data = vector_store.get_all_data()

    if not data["ids"]:
        raise ValueError("ChromaDB koleksiyonu boş. Önce verileri yükleyin.")

    has_metadatas = data.get("metadatas") is not None and len(data["metadatas"]) > 0
    has_documents = data.get("documents") is not None and len(data["documents"]) > 0
    has_embeddings = data.get("embeddings") is not None and len(data["embeddings"]) > 0

    records = []
    for i in range(len(data["ids"])):
        metadata = data["metadatas"][i] if has_metadatas else {}
        doc = data["documents"][i] if has_documents else ""
        emb = list(data["embeddings"][i]) if has_embeddings else []

        record = {
            "url": metadata.get("url", ""),
            "chunk_text": doc,
            "chunk_vector": emb,
            "title": metadata.get("title", ""),
            "source": metadata.get("source", ""),
            "parent_id": metadata.get("parent_id", ""),
            "chunk_index": metadata.get("chunk_index", 0),
        }
        records.append(record)

    df = pd.DataFrame(records)
    logger.info(f"DataFrame oluşturuldu: {len(df)} satır, {len(df.columns)} kolon")

    return df


def push_to_hub(
    df: pd.DataFrame,
    repo_name: str,
    private: bool = True,
):
    """
    DataFrame'i Hugging Face Dataset olarak yükler.

    Args:
        df: Export edilecek DataFrame.
        repo_name: HF repo adı (ör. "username/repo-name").
        private: Repo gizli olsun mu.
    """
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError(
            "HF_TOKEN bulunamadı. .env dosyasına veya environment'a ekleyin."
        )

    logger.info(f"Hugging Face Dataset oluşturuluyor: {repo_name}")
    dataset = Dataset.from_pandas(df)

    logger.info(f"Dataset push ediliyor: {repo_name} (private={private})")
    dataset.push_to_hub(
        repo_name,
        token=token,
        private=private,
    )

    logger.info(f"✅ Dataset başarıyla yüklendi: https://huggingface.co/datasets/{repo_name}")


def export_to_parquet(df: pd.DataFrame, output_path: str = None):
    """
    DataFrame'i local parquet dosyası olarak kaydeder.

    Args:
        df: Export edilecek DataFrame.
        output_path: Çıktı dosya yolu. None ise data/export/ altına kaydedilir.
    """
    if output_path is None:
        export_dir = PROJECT_ROOT / "data" / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = export_dir / "chunked_vectors.parquet"

    df.to_parquet(str(output_path), index=False)
    logger.info(f"Parquet dosyası kaydedildi: {output_path}")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="ChromaDB → HF Dataset Export")
    parser.add_argument(
        "--repo",
        type=str,
        help="Hugging Face repo adı (ör. 'username/turkish-medical-chunks')",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        default=True,
        help="Repo'yu private olarak oluştur (varsayılan: True)",
    )
    parser.add_argument(
        "--parquet-only",
        action="store_true",
        help="Sadece local parquet olarak kaydet, HF'ye push etme",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ChromaDB → Hugging Face Dataset Export")
    print("=" * 60)

    # 1. ChromaDB'den verileri çek
    df = export_to_dataframe()
    print(f"\nExport edilen chunk sayısı: {len(df)}")
    print(f"Kolonlar: {list(df.columns)}")

    # 2. Local parquet olarak kaydet
    export_to_parquet(df)

    # 3. HF'ye push et (opsiyonel)
    if not args.parquet_only and args.repo:
        push_to_hub(df, args.repo, args.private)
    elif not args.parquet_only:
        print(
            "\n⚠️  HF'ye push etmek için --repo parametresi gerekli.\n"
            "   Örnek: python export_to_hf.py --repo username/turkish-medical-chunks"
        )
