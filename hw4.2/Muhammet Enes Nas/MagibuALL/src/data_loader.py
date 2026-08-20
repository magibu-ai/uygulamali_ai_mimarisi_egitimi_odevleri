"""
data_loader.py — Hugging Face'den Türkçe tıbbi makale veri seti yükleme ve örnekleme.

Dataset: alibayram/turkish-hospital-medical-articles
Şema: url, title, headings, text, publish_date, update_date
"""

import os
import logging
from pathlib import Path

from datasets import load_dataset, concatenate_datasets
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

# Denenecek dataset isimleri (hangisi çalışırsa o kullanılacak)
DATASET_CANDIDATES = [
    "alibayram/turkish-hospital-medical-articles",
    "umutertugrul/turkish-hospital-medical-articles",
]

# Seçilecek hastane split'leri
DEFAULT_SPLITS = ["acibadem", "memorial"]

# Örneklenecek makale sayısı
DEFAULT_SAMPLE_SIZE = 500

# Minimum metin uzunluğu (karakter) — çok kısa makaleleri filtrelemek için
MIN_TEXT_LENGTH = 200


def get_hf_token():
    """Hugging Face token'ını environment'tan alır."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        logger.warning(
            "HF_TOKEN bulunamadı. Gated dataset'lere erişim için "
            ".env dosyasına veya environment'a HF_TOKEN eklemelisiniz."
        )
    return token


def load_hospital_data(
    splits=None,
    sample_size=DEFAULT_SAMPLE_SIZE,
    seed=42,
):
    """
    Hugging Face'den hastane makalelerini yükler ve örnekler.

    Args:
        splits: Yüklenecek hastane split'leri (ör. ["acibadem", "memorial"]).
                None ise DEFAULT_SPLITS kullanılır.
        sample_size: Örneklenecek makale sayısı.
        seed: Rastgele örnekleme seed'i (tekrarlanabilirlik için).

    Returns:
        datasets.Dataset: Örneklenmiş ve filtrelenmiş dataset.
    """
    if splits is None:
        splits = DEFAULT_SPLITS

    token = get_hf_token()

    # Dataset'i yüklemeyi dene
    dataset = None
    used_name = None

    for dataset_name in DATASET_CANDIDATES:
        try:
            logger.info(f"Dataset yükleniyor: {dataset_name}")
            all_splits = []

            for split_name in splits:
                logger.info(f"  Split yükleniyor: {split_name}")
                ds = load_dataset(
                    dataset_name,
                    split=split_name,
                    token=token,
                )
                # Kaynak hastane bilgisini metadata olarak ekle
                ds = ds.map(
                    lambda x: {"source": split_name},
                    desc=f"Adding source: {split_name}",
                )
                all_splits.append(ds)

            dataset = concatenate_datasets(all_splits)
            used_name = dataset_name
            logger.info(
                f"Dataset başarıyla yüklendi: {used_name} "
                f"({len(dataset)} makale, split'ler: {splits})"
            )
            break

        except Exception as e:
            logger.warning(f"{dataset_name} yüklenemedi: {e}")
            continue

    if dataset is None:
        raise RuntimeError(
            "Hiçbir dataset kaynağından veri yüklenemedi. "
            "HF_TOKEN'ınızı kontrol edin ve dataset erişim izninizi onaylayın."
        )

    # Boş ve kısa metinleri filtrele
    original_count = len(dataset)
    dataset = dataset.filter(
        lambda x: x["text"] is not None and len(x["text"].strip()) >= MIN_TEXT_LENGTH,
        desc="Kısa/boş metinler filtreleniyor",
    )
    filtered_count = original_count - len(dataset)
    if filtered_count > 0:
        logger.info(f"{filtered_count} kısa/boş makale filtrelendi.")

    # Örnekleme
    if len(dataset) > sample_size:
        dataset = dataset.shuffle(seed=seed).select(range(sample_size))
        logger.info(f"{sample_size} makale rastgele örneklendi.")
    else:
        logger.info(
            f"Dataset zaten {len(dataset)} makale içeriyor "
            f"(hedef: {sample_size}), tamamı kullanılacak."
        )

    return dataset


def save_raw_data(dataset, output_dir=None):
    """
    Ham veriyi parquet formatında kaydeder.

    Args:
        dataset: Kaydedilecek HF dataset.
        output_dir: Çıktı dizini. None ise data/raw/ kullanılır.
    """
    if output_dir is None:
        output_dir = RAW_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "sampled_articles.parquet"
    dataset.to_parquet(str(output_path))
    logger.info(f"Ham veri kaydedildi: {output_path} ({len(dataset)} makale)")

    return output_path


def load_raw_data(input_path=None):
    """
    Daha önce kaydedilmiş ham veriyi yükler.

    Args:
        input_path: Parquet dosya yolu. None ise varsayılan yol kullanılır.

    Returns:
        datasets.Dataset
    """
    if input_path is None:
        input_path = RAW_DIR / "sampled_articles.parquet"

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Ham veri dosyası bulunamadı: {input_path}. "
            "Önce 'python main.py --step load' çalıştırın."
        )

    from datasets import Dataset
    import pandas as pd

    df = pd.read_parquet(str(input_path))
    dataset = Dataset.from_pandas(df)
    logger.info(f"Ham veri yüklendi: {input_path} ({len(dataset)} makale)")

    return dataset


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("Veri Yükleme Modülü — Test")
    print("=" * 60)

    ds = load_hospital_data()
    print(f"\nYüklenen makale sayısı: {len(ds)}")
    print(f"Kolonlar: {ds.column_names}")
    print(f"\nÖrnek makale başlığı: {ds[0]['title']}")
    print(f"Metin uzunluğu: {len(ds[0]['text'])} karakter")

    path = save_raw_data(ds)
    print(f"\nKaydedilen dosya: {path}")
