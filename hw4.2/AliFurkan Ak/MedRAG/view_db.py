import sys
import logging
import chromadb
import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def view_chroma_contents(
    persist_dir: str = config.CHROMA_PATH,
    collection_name: str = config.COLLECTION_NAME
):
    """
    Displays all collections and persisted records in local ChromaDB.
    """
    print("=" * 70)
    print(f" ChromaDB Vector Store Inspector ({persist_dir}) ")
    print("=" * 70)

    client = chromadb.PersistentClient(path=persist_dir)
    collections = client.list_collections()

    print(f"\n[+] Active Collections Count: {len(collections)}")
    for col in collections:
        print(f" - Collection Name: {col.name} | Items Count: {col.count()}")

    print("\n" + "-" * 70)
    print(f" Target Collection: '{collection_name}' ")
    print("-" * 70)

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"[-] Collection '{collection_name}' not found: {e}")
        return

    total_count = collection.count()
    print(f"Total Record Count: {total_count}\n")

    if total_count == 0:
        print("Vector database currently contains no records.")
        return

    all_data = collection.get(include=["documents", "metadatas", "embeddings"])

    ids = all_data.get("ids", [])
    documents = all_data.get("documents", [])
    metadatas = all_data.get("metadatas", [])
    embeddings = all_data.get("embeddings", [])

    for i in range(len(ids)):
        chunk_id = ids[i]
        doc = documents[i] if documents else "N/A"
        meta = metadatas[i] if metadatas else {}
        url = meta.get("url") if meta else None
        vector = embeddings[i] if embeddings is not None and len(embeddings) > i else None
        vec_dim = len(vector) if vector is not None else "N/A"

        print(f"[+] Record #{i+1}")
        print(f"  • ID            : {chunk_id}")
        print(f"  • Source URL    : {url if url else '(None / Null)'}")
        print(f"  • Text (Chunk)  : {doc}")
        print(f"  • Vector Dim    : {vec_dim}")
        if vector is not None:
            print(f"  • Vector (First 5): {vector[:5]}...")
        print("-" * 70)

if __name__ == "__main__":
    view_chroma_contents()
