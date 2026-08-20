"""
chunking.py — Türkçe tıbbi makaleleri hibrit yöntemle chunk'lama.

Strateji: RecursiveCharacterTextSplitter (tiktoken tabanlı)
- Chunk boyutu: 512 token
- Overlap: 64 token
- Öncelik: paragraf sınırları → satır → cümle → kelime
"""

import hashlib
import logging
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Chunking parametreleri
CHUNK_SIZE = 512       # token
CHUNK_OVERLAP = 64     # token
ENCODING_NAME = "cl100k_base"  # tiktoken encoding

# Bölme sırası: paragraf → satır → cümle → kelime → karakter
SEPARATORS = ["\n\n", "\n", ". ", ", ", " ", ""]


def create_text_splitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
):
    """
    Tiktoken tabanlı RecursiveCharacterTextSplitter oluşturur.

    Args:
        chunk_size: Chunk başına maksimum token sayısı.
        chunk_overlap: Chunk'lar arası örtüşme token sayısı.

    Returns:
        RecursiveCharacterTextSplitter instance.
    """
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=ENCODING_NAME,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
    )
    return splitter


def generate_chunk_id(text, parent_id, chunk_index):
    """
    Chunk için benzersiz, deterministik ID üretir.

    Args:
        text: Chunk metni.
        parent_id: Üst makale ID'si.
        chunk_index: Makale içindeki chunk sırası.

    Returns:
        str: Benzersiz chunk ID'si.
    """
    raw = f"{parent_id}_{chunk_index}_{text[:100]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def chunk_article(article, article_index, splitter=None):
    """
    Tek bir makaleyi chunk'lara ayırır.

    Args:
        article: Dict veya HF dataset row (text, title, url, source alanları).
        article_index: Makale index'i (parent_id olarak kullanılır).
        splitter: TextSplitter instance. None ise yeni oluşturulur.

    Returns:
        List[Dict]: Her chunk için {"chunk_id", "text", "metadata"} dict listesi.
    """
    if splitter is None:
        splitter = create_text_splitter()

    text = article.get("text", "").strip()
    if not text:
        return []

    title = article.get("title", "Başlıksız")
    url = article.get("url", "")
    source = article.get("source", "bilinmiyor")
    parent_id = f"article_{article_index}"

    # Metni chunk'lara ayır
    chunk_texts = splitter.split_text(text)

    chunks = []
    for i, chunk_text in enumerate(chunk_texts):
        chunk_id = generate_chunk_id(chunk_text, parent_id, i)
        chunks.append({
            "chunk_id": chunk_id,
            "text": chunk_text,
            "metadata": {
                "title": title,
                "url": url,
                "source": source,
                "parent_id": parent_id,
                "chunk_index": i,
                "total_chunks": len(chunk_texts),
            },
        })

    return chunks


def chunk_dataset(dataset, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """
    Tüm dataset'i chunk'lara ayırır.

    Args:
        dataset: HF Dataset (text, title, url, source alanları).
        chunk_size: Chunk başına maksimum token sayısı.
        chunk_overlap: Chunk'lar arası örtüşme token sayısı.

    Returns:
        List[Dict]: Tüm chunk'ların listesi.
    """
    splitter = create_text_splitter(chunk_size, chunk_overlap)

    all_chunks = []
    articles_with_no_chunks = 0

    for idx in range(len(dataset)):
        article = dataset[idx]
        chunks = chunk_article(article, idx, splitter)

        if not chunks:
            articles_with_no_chunks += 1
            continue

        all_chunks.extend(chunks)

    logger.info(
        f"Chunking tamamlandı: {len(dataset)} makale → {len(all_chunks)} chunk "
        f"(chunk_size={chunk_size}, overlap={chunk_overlap})"
    )

    if articles_with_no_chunks > 0:
        logger.warning(
            f"{articles_with_no_chunks} makale boş metin nedeniyle atlandı."
        )

    # İstatistikler
    chunk_lengths = [len(c["text"]) for c in all_chunks]
    if chunk_lengths:
        avg_len = sum(chunk_lengths) / len(chunk_lengths)
        min_len = min(chunk_lengths)
        max_len = max(chunk_lengths)
        logger.info(
            f"Chunk istatistikleri (karakter): "
            f"ortalama={avg_len:.0f}, min={min_len}, max={max_len}"
        )

    return all_chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("Chunking Modülü — Test")
    print("=" * 60)

    # Örnek bir makale ile test
    test_article = {
        "text": (
            "Diyabet, kan şekeri seviyelerinin normalin üzerinde olduğu kronik bir hastalıktır. "
            "Tip 1 diyabet, pankreasın yeterli insülin üretmemesi nedeniyle oluşur. "
            "Tip 2 diyabet ise vücudun insüline karşı direnç geliştirmesiyle ortaya çıkar.\n\n"
            "Diyabetin belirtileri arasında sık idrara çıkma, aşırı susama, "
            "açıklanamayan kilo kaybı ve yorgunluk sayılabilir. "
            "Erken teşhis ve tedavi, komplikasyonların önlenmesinde kritik öneme sahiptir.\n\n"
            "Tedavi seçenekleri arasında insülin tedavisi, oral antidiyabetik ilaçlar, "
            "diyet ve egzersiz programları yer alır. Hastaların düzenli kan şekeri "
            "takibi yapması ve sağlıklı yaşam tarzı benimsemesi önerilir."
        ),
        "title": "Diyabet Hastalığı Hakkında Bilmeniz Gerekenler",
        "url": "https://example.com/diyabet",
        "source": "acibadem",
    }

    chunks = chunk_article(test_article, 0)
    print(f"\nMakale: {test_article['title']}")
    print(f"Metin uzunluğu: {len(test_article['text'])} karakter")
    print(f"Üretilen chunk sayısı: {len(chunks)}")

    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"ID: {chunk['chunk_id']}")
        print(f"Uzunluk: {len(chunk['text'])} karakter")
        print(f"Metin: {chunk['text'][:150]}...")
        print(f"Metadata: {chunk['metadata']}")
