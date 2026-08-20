import re
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import config
from ollama_embedder import OllamaEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SemanticChunker:
    """
    Splits documents into coherent semantic chunks based on topic shifts (Semantic Breakpoints)
    calculated from sentence embedding Cosine Distances using Ollama.
    """

    def __init__(
        self,
        embedder: Optional[OllamaEmbedder] = None,
        threshold_percentile: float = config.SEMANTIC_THRESHOLD_PERCENTILE,
        min_chunk_len: int = config.MIN_CHUNK_CHAR_LEN,
        max_chunk_len: int = config.MAX_CHUNK_CHAR_LEN
    ):
        self.embedder = embedder or OllamaEmbedder()
        self.threshold_percentile = threshold_percentile
        self.min_chunk_len = min_chunk_len
        self.max_chunk_len = max_chunk_len

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Splits raw text into clean discrete sentences based on punctuation and line breaks.
        """
        raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        sentences = [s.strip() for s in raw_sentences if s and len(s.strip()) > 10]
        return sentences

    @staticmethod
    def _cosine_distance(v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculates Cosine Distance (1.0 - CosineSimilarity) between two vectors."""
        dot = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 1.0
        similarity = dot / (norm1 * norm2)
        return float(1.0 - similarity)

    def chunk_document(
        self,
        text: str,
        url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Processes a document:
        1. Segments text into sentences.
        2. Generates sentence vector embeddings via Ollama batch API.
        3. Calculates Cosine Distances between consecutive sentence vectors.
        4. Detects Breakpoints at semantic topic shift thresholds.
        5. Groups sentences into chunks and extracts chunk vectors.
        """
        sentences = self.split_into_sentences(text)
        if not sentences:
            return []

        if len(sentences) == 1:
            vec = self.embedder.get_embedding(sentences[0])
            return [{
                "url": url,
                "chunk_text": sentences[0],
                "chunk_vector": vec
            }]

        logger.info(f"Document segmented into {len(sentences)} sentences. Requesting embeddings from Ollama...")

        # 1. Batch generate sentence vectors
        sentence_vectors = [np.array(v, dtype=np.float32) for v in self.embedder.get_embeddings(sentences)]

        # 2. Compute distances between consecutive sentence vectors
        distances = []
        for i in range(len(sentence_vectors) - 1):
            dist = self._cosine_distance(sentence_vectors[i], sentence_vectors[i+1])
            distances.append(dist)

        # 3. Determine breakpoint distance threshold
        if distances:
            threshold = float(np.percentile(distances, self.threshold_percentile))
        else:
            threshold = config.DEFAULT_DISTANCE_THRESHOLD

        logger.info(f"Semantic Distance Threshold ({self.threshold_percentile}th Percentile): {threshold:.4f}")

        # 4. Identify Breakpoints and group sentences
        chunks_sentences = []
        current_chunk_sents = [sentences[0]]

        for i, dist in enumerate(distances):
            curr_len = sum(len(s) for s in current_chunk_sents)
            
            if (dist >= threshold and curr_len >= self.min_chunk_len) or curr_len >= self.max_chunk_len:
                chunks_sentences.append(" ".join(current_chunk_sents))
                current_chunk_sents = [sentences[i+1]]
            else:
                current_chunk_sents.append(sentences[i+1])

        if current_chunk_sents:
            chunks_sentences.append(" ".join(current_chunk_sents))

        logger.info(f"Document semantically chunked into {len(chunks_sentences)} chunks.")

        # 5. Extract final embeddings for the generated chunks
        chunk_embeddings = self.embedder.get_embeddings(chunks_sentences)

        result_chunks = []
        for i, chunk_txt in enumerate(chunks_sentences):
            result_chunks.append({
                "url": url,
                "chunk_text": chunk_txt,
                "chunk_vector": chunk_embeddings[i]
            })

        return result_chunks


if __name__ == "__main__":
    sample_article = """
    Diyabet (şeker hastalığı), insülin hormonunun üretilememesi veya hücreler tarafından verimli kullanılamaması durumudur. 
    Tip 1 diyabet genellikle çocukluk çağında bağışıklık sisteminin pankreas hücrelerine saldırmasıyla ortaya çıkar.
    Tip 2 diyabet ise yetişkinlerde aşırı kilo, pasif yaşam tarzı ve genetik faktörler sonucunda gelişir.
    
    Yapay zekâ ve derin öğrenme modelleri son yıllarda tıbbi görüntüleme alanında büyük başarılar yakalamıştır.
    Radyologların akciğer grafilerindeki tümörleri tespit etmesine yardımcı olan yapay zeka algoritmaları geliştirilmiştir.
    Özellikle evrişimli sinir ağları (CNN) medikal görüntü analizinde standart hale gelmiştir.
    """

    chunker = SemanticChunker()
    chunks = chunker.chunk_document(sample_article, url="https://example.com/test-makale")

    print("\n" + "="*70)
    print(f" Semantic Chunking Result ({len(chunks)} Chunks Generated) ")
    print("="*70)
    for idx, c in enumerate(chunks, 1):
        print(f"\n🧩 Chunk #{idx} (Char Length: {len(c['chunk_text'])}, Vector Dim: {len(c['chunk_vector'])})")
        print(f" URL: {c['url']}")
        print(f" Text: {c['chunk_text']}")
