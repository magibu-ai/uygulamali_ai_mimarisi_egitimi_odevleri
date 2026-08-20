"""PDF tabanli ChromaDB aramasi ve kaynak sayfasi gorseli."""

import os
from pathlib import Path

import chromadb
import pymupdf
import requests

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "chroma_db"
IMAGE_PATH = ROOT / "source_pages"
COLLECTION = "maciocia_foundations_bge_m3"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3:latest")
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.45"))


def pdf_path() -> Path:
    path = os.getenv("ACUPUNCTURE_PDF")
    if not path:
        raise RuntimeError("ACUPUNCTURE_PDF ortam degiskeni ayarlanmamis.")
    pdf = Path(path).expanduser()
    if not pdf.is_file():
        raise RuntimeError(f"PDF bulunamadi: {pdf}")
    return pdf


def embed(texts: list[str]) -> list[list[float]]:
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/embed",
            json={"model": EMBED_MODEL, "input": texts},
            timeout=600,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama embedding hatasi: {exc}") from exc
    return response.json()["embeddings"]


def collection():
    return chromadb.PersistentClient(path=str(DB_PATH)).get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"}, embedding_function=None
    )


def chunk_text(text: str, size: int = 260, overlap: int = 50) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[start : start + size])
        for start in range(0, len(words), size - overlap)
        if words[start : start + size]
    ]


def search(query: str, k: int = 5) -> list[dict]:
    db = collection()
    if not db.count():
        raise RuntimeError("Indeks bos. Once 'python index.py' calistirin.")
    result = db.query(
        query_embeddings=embed([query]),
        n_results=min(k, db.count()),
        include=["documents", "metadatas", "distances"],
    )
    return [
        {"text": text, **meta, "similarity": round(1 - distance, 3)}
        for text, meta, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ) if 1 - distance >= MIN_SIMILARITY
    ]


def render_page(pdf_page: int) -> str:
    IMAGE_PATH.mkdir(exist_ok=True)
    output = IMAGE_PATH / f"pdf-page-{pdf_page}.png"
    if not output.exists():
        document = pymupdf.open(pdf_path())
        page = document.load_page(pdf_page - 1)
        page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(output)
        document.close()
    return str(output.resolve())
