import os
import re
import uuid
import logging
from typing import List, Dict, Any, Optional
import chromadb
import numpy as np
from rank_bm25 import BM25Okapi
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional Reranker import with graceful fallback
try:
    from sentence_transformers import CrossEncoder
    HAS_CROSS_ENCODER = True
except ImportError:
    HAS_CROSS_ENCODER = False


def tokenize_turkish_text(text: str) -> List[str]:
    """Basic Turkish/lower tokenization for BM25 indexing."""
    text_clean = re.sub(r'[^\w\s]', ' ', text.lower())
    tokens = [t.strip() for t in text_clean.split() if len(t.strip()) > 1]
    return tokens


class LocalVectorDB:
    """
    Local ChromaDB Vector DB Manager enhanced with:
    1. Dense Vector Cosine Similarity Search (Ollama embeddinggemma:300m)
    2. BM25 Keyword Search + Reciprocal Rank Fusion (RRF)
    3. Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2)
    4. Similarity Threshold Safety Gate (config.SIMILARITY_THRESHOLD)
    """

    def __init__(
        self,
        persist_dir: str = config.CHROMA_PATH,
        collection_name: str = config.COLLECTION_NAME
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        os.makedirs(self.persist_dir, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(
            f"ChromaDB collection ready: '{self.collection_name}' "
            f"(Current record count: {self.collection.count()})"
        )

        # Initialize BM25 and Reranker
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_doc_ids: List[str] = []
        self.bm25_documents: List[Dict[str, Any]] = []
        self._build_bm25_index()

        self.reranker_model = None
        if config.USE_RERANKER and HAS_CROSS_ENCODER:
            try:
                logger.info(f"Loading Cross-Encoder Reranker model: '{config.RERANKER_MODEL_NAME}'...")
                self.reranker_model = CrossEncoder(config.RERANKER_MODEL_NAME)
                logger.info("Cross-Encoder Reranker loaded successfully.")
            except Exception as e:
                logger.warning(f"Failed to load Reranker model: {e}")

    def _build_bm25_index(self):
        """Builds or refreshes the in-memory BM25 index from ChromaDB documents."""
        count = self.collection.count()
        if count == 0:
            self.bm25_index = None
            self.bm25_doc_ids = []
            self.bm25_documents = []
            return

        all_data = self.collection.get(include=["documents", "metadatas"])
        ids = all_data.get("ids", [])
        documents = all_data.get("documents", [])
        metadatas = all_data.get("metadatas", [])

        tokenized_corpus = []
        self.bm25_doc_ids = ids
        self.bm25_documents = []

        for i in range(len(ids)):
            doc_text = documents[i]
            meta = metadatas[i] if metadatas else {}
            self.bm25_documents.append({
                "chunk_id": ids[i],
                "chunk_text": doc_text,
                "url": meta.get("url", "")
            })
            tokenized_corpus.append(tokenize_turkish_text(doc_text))

        if tokenized_corpus:
            self.bm25_index = BM25Okapi(tokenized_corpus)
            logger.info(f"BM25 index built with {len(ids)} documents.")

    def add_chunk(
        self,
        chunk_text: str,
        chunk_vector: List[float],
        url: Optional[str] = None,
        chunk_id: Optional[str] = None
    ) -> str:
        """Inserts a single chunk into ChromaDB and updates BM25 index."""
        cid = chunk_id or str(uuid.uuid4())
        metadata = {"url": url if url is not None else ""}

        self.collection.add(
            ids=[cid],
            embeddings=[chunk_vector],
            documents=[chunk_text],
            metadatas=[metadata]
        )
        self._build_bm25_index()
        logger.info(f"Chunk inserted successfully ID: {cid}")
        return cid

    def add_chunks_batch(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Inserts a batch of chunks into ChromaDB and updates BM25 index."""
        if not chunks:
            return []

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for item in chunks:
            cid = item.get("chunk_id") or str(uuid.uuid4())
            url_val = item.get("url")
            
            ids.append(cid)
            documents.append(item["chunk_text"])
            embeddings.append(item["chunk_vector"])
            metadatas.append({"url": url_val if url_val is not None else ""})

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        self._build_bm25_index()
        logger.info(f"Batch inserted {len(chunks)} chunks into ChromaDB.")
        return ids

    def _bm25_search(self, query_text: str, top_k: int = 15) -> List[Dict[str, Any]]:
        """Executes BM25 keyword search over tokenized corpus."""
        if not self.bm25_index or not self.bm25_documents:
            return []

        tokens = tokenize_turkish_text(query_text)
        if not tokens:
            return []

        scores = self.bm25_index.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                item = dict(self.bm25_documents[idx])
                item["bm25_score"] = float(scores[idx])
                results.append(item)

        return results

    def search(
        self,
        query_vector: List[float],
        top_k: int = 3,
        similarity_threshold: Optional[float] = config.SIMILARITY_THRESHOLD,
        query_text: Optional[str] = None,
        use_hybrid: bool = config.USE_HYBRID_SEARCH,
        use_reranker: bool = config.USE_RERANKER
    ) -> List[Dict[str, Any]]:
        """
        Executes Advanced Hybrid Retrieval & Reranking:
        1. Fetch candidates via Vector Search (Ollama embeddinggemma:300m)
        2. Fetch candidates via BM25 Keyword Search (if query_text provided & use_hybrid)
        3. Fuse ranks via Reciprocal Rank Fusion (RRF)
        4. Re-score top candidates using Cross-Encoder Reranker
        5. Apply Similarity Threshold Safety Gate
        """
        candidates_k = config.RETRIEVAL_CANDIDATES_K if (use_hybrid or use_reranker) else top_k

        # 1. Vector Search (Dense Retrieval)
        vector_raw = self.collection.query(
            query_embeddings=[query_vector],
            n_results=min(candidates_k, max(1, self.collection.count())),
            include=["documents", "metadatas", "distances", "embeddings"]
        )

        if not vector_raw or not vector_raw.get("ids") or not vector_raw["ids"][0]:
            return []

        v_ids = vector_raw["ids"][0]
        v_docs = vector_raw["documents"][0]
        v_metas = vector_raw["metadatas"][0]
        v_dists = vector_raw["distances"][0]
        v_embeds = vector_raw["embeddings"][0] if vector_raw.get("embeddings") else [None] * len(v_ids)

        vector_results = {}
        for i in range(len(v_ids)):
            dist = v_dists[i]
            sim_score = round(float(1.0 - dist), 4)
            url_val = v_metas[i].get("url", "")
            vector_results[v_ids[i]] = {
                "chunk_id": v_ids[i],
                "url": url_val if url_val != "" else None,
                "chunk_text": v_docs[i],
                "chunk_vector": v_embeds[i],
                "similarity_score": sim_score,
                "distance": round(float(dist), 4),
                "vector_rank": i + 1
            }

        # 2. Hybrid Search Fusion (RRF - Reciprocal Rank Fusion)
        final_candidates = []
        if use_hybrid and query_text and self.bm25_index:
            bm25_matches = self._bm25_search(query_text, top_k=candidates_k)
            bm25_dict = {item["chunk_id"]: (i + 1) for i, item in enumerate(bm25_matches)}

            # Combine all candidate IDs
            all_candidate_ids = set(vector_results.keys()).union(set(bm25_dict.keys()))

            rrf_scores = {}
            rrf_k = config.RRF_K
            for cid in all_candidate_ids:
                v_rank = vector_results[cid]["vector_rank"] if cid in vector_results else 999
                b_rank = bm25_dict[cid] if cid in bm25_dict else 999

                rrf_val = (1.0 / (rrf_k + v_rank)) + (1.0 / (rrf_k + b_rank))
                rrf_scores[cid] = rrf_val

            # Sort candidate IDs by RRF score
            sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:candidates_k]

            for cid in sorted_ids:
                if cid in vector_results:
                    item = vector_results[cid]
                else:
                    # Fetch document from BM25 corpus if not in vector top results
                    bm_doc = next(d for d in self.bm25_documents if d["chunk_id"] == cid)
                    item = {
                        "chunk_id": cid,
                        "url": bm_doc["url"] if bm_doc["url"] != "" else None,
                        "chunk_text": bm_doc["chunk_text"],
                        "chunk_vector": None,
                        "similarity_score": 0.0,
                        "distance": 1.0,
                        "vector_rank": 999
                    }
                item["rrf_score"] = round(float(rrf_scores[cid]), 6)
                final_candidates.append(item)
        else:
            final_candidates = list(vector_results.values())

        # 3. Cross-Encoder Reranking
        if use_reranker and query_text and self.reranker_model and final_candidates:
            try:
                pairs = [[query_text, item["chunk_text"]] for item in final_candidates]
                rerank_scores = self.reranker_model.predict(pairs)

                for i, item in enumerate(final_candidates):
                    item["rerank_score"] = round(float(rerank_scores[i]), 4)

                # Sort by rerank score descending
                final_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            except Exception as e:
                logger.warning(f"Reranker scoring warning: {e}")

        # 4. Final Similarity Threshold Safety Gate
        filtered_results = []
        for item in final_candidates:
            sim = item.get("similarity_score", 0.0)
            if similarity_threshold is not None and sim < similarity_threshold:
                continue
            filtered_results.append(item)

        return filtered_results[:top_k]

    def count(self) -> int:
        """Returns total record count in ChromaDB collection."""
        return self.collection.count()

    def reset(self):
        """Clears and recreates the ChromaDB collection & BM25 index."""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._build_bm25_index()
            logger.info(f"Collection '{self.collection_name}' reset successfully.")
        except Exception as e:
            logger.warning(f"Reset collection warning: {e}")
