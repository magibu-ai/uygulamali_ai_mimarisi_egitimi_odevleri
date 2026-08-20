import os

# Ollama Service Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "embeddinggemma:300m")

# ChromaDB Vector Database Configuration
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "medical_chunks")

# Semantic Chunking Configuration
SEMANTIC_THRESHOLD_PERCENTILE = float(os.getenv("SEMANTIC_THRESHOLD_PERCENTILE", "85"))
DEFAULT_DISTANCE_THRESHOLD = float(os.getenv("DEFAULT_DISTANCE_THRESHOLD", "0.35"))
MIN_CHUNK_CHAR_LEN = int(os.getenv("MIN_CHUNK_CHAR_LEN", "150"))
MAX_CHUNK_CHAR_LEN = int(os.getenv("MAX_CHUNK_CHAR_LEN", "1200"))

# Vector Search Similarity Threshold Configuration
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.48"))

# Hybrid Search (BM25 + Vector + RRF) Configuration
USE_HYBRID_SEARCH = os.getenv("USE_HYBRID_SEARCH", "True").lower() == "true"
RETRIEVAL_CANDIDATES_K = int(os.getenv("RETRIEVAL_CANDIDATES_K", "15"))
RRF_K = int(os.getenv("RRF_K", "60"))

# Reranking (Cross-Encoder) Configuration
USE_RERANKER = os.getenv("USE_RERANKER", "True").lower() == "true"
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Generative LLM Configuration (Chatbot Synthesis Layer)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen2.5:7b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
ENABLE_GENERATIVE_RAG = os.getenv("ENABLE_GENERATIVE_RAG", "True").lower() == "true"

