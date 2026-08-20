"""Central configuration for the Turkish medical vector-search pipeline.

Every tunable lives here so the build / search / eval scripts stay in sync and
the README can point to a single source of truth.
"""
from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
CHROMA_DIR = ROOT / "chroma_db"

CHUNKS_PARQUET = DATA_DIR / "chunks.parquet"          # HF-delivery table (url, chunk_text, chunk_vector, ...)
TEST_QUESTIONS = DATA_DIR / "test_questions.json"      # 20 positive + 10 negative
BENCHMARK_JSON = OUTPUT_DIR / "benchmark_results.json"
THRESHOLD_CSV = OUTPUT_DIR / "threshold_analysis.csv"

# --- Data source -----------------------------------------------------------
# Gated HF dataset — access is auto-granted after accepting the terms while
# logged in (huggingface-cli login).  We scope to a single hospital (Acibadem)
# for a clean, self-consistent corpus, per the "belirli bir hastane" option.
DATASET_REPO = "umutertugrul/turkish-hospital-medical-articles"
HOSPITAL_FILE = "data/acibadem-00000-of-00001.parquet"
SOURCE_NAME = "acibadem"

N_ARTICLES = 250          # articles sampled (spec range: 100–1000)
MIN_ARTICLE_CHARS = 500   # drop stubs
RANDOM_SEED = 42          # reproducible sampling

# --- Embedding model -------------------------------------------------------
# magibu/embeddingmagibu-200m: Turkish-focused, Gemma3-based distilled encoder.
# 768-dim output, 8192-token context, produces L2-normalised vectors.
EMBED_MODEL = "magibu/embeddingmagibu-200m"
EMBED_DIM = 768
NORMALIZE = True          # unit vectors -> dot product == cosine similarity

# --- Chunking (paragraph/sentence-aware, token-budgeted, with overlap) -----
MAX_TOKENS_PER_CHUNK = 384
CHUNK_OVERLAP_TOKENS = 64
MIN_CHUNK_TOKENS = 24     # discard trailing scraps

# --- Vector store ----------------------------------------------------------
COLLECTION_NAME = "acibadem_medical"
DISTANCE_SPACE = "cosine"  # Chroma distance = 1 - cosine_similarity

# --- Search & threshold ----------------------------------------------------
TOP_K = 5
# Cosine-similarity gate: queries whose best match scores below this are
# answered with the "not in my documents" refusal instead of a retrieved chunk.
# The value below is the empirical optimum found by src/evaluate.py — see the
# threshold analysis in README.md.
SIMILARITY_THRESHOLD = 0.49

REFUSAL_MESSAGE = "Bu sorunun cevabı dokümanlarımda yer almamaktadır."
