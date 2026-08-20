"""Maciocia PDF'ini bir kez ChromaDB'ye indeksler."""

import argparse
import time

from pypdf import PdfReader

import rag

BATCH_SIZE = 48


def main(reset: bool = False) -> None:
    pdf = rag.pdf_path()
    reader = PdfReader(pdf)
    db = rag.collection()
    if db.count() and not reset:
        print(f"Indeks zaten hazir: {db.count()} parca. Yenilemek icin --reset kullanin.")
        return
    if reset:
        rag.chromadb.PersistentClient(path=str(rag.DB_PATH)).delete_collection(rag.COLLECTION)
        db = rag.collection()

    started = time.time()
    pending: list[tuple[str, str, dict]] = []
    total = 0
    for page_index, page in enumerate(reader.pages):
        pdf_page = page_index + 1
        # ponytail: Kitabin ana govdesinde basili sayfa PDF sayfasindan 29 geride.
        # Yeni baski kullanilirsa metadata cikarimi gelistirilmeli.
        book_page = pdf_page - 29 if 31 <= pdf_page <= 1295 else "on/arka kisim"
        for chunk_index, chunk in enumerate(rag.chunk_text(page.extract_text() or "")):
            pending.append(
                (
                    f"p{pdf_page}-c{chunk_index}",
                    chunk,
                    {"pdf_page": pdf_page, "book_page": book_page},
                )
            )
        if pending and (len(pending) >= BATCH_SIZE or pdf_page == len(reader.pages)):
            ids, texts, metadata = map(list, zip(*pending))
            db.upsert(ids=ids, documents=texts, metadatas=metadata, embeddings=rag.embed(texts))
            total += len(pending)
            pending.clear()
            print(f"{pdf_page}/{len(reader.pages)} sayfa, {total} parca", end="\r")
    print(f"\nBitti: {total} parca, {time.time() - started:.0f} saniye.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    main(parser.parse_args().reset)
