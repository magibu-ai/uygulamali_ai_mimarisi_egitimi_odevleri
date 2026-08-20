project/
│
├── CLAUDE.md
├── ROADMAP.md
├── PROMPT.md
├── README.md
├── pyproject.toml
├── requirements.txt
│
├── configs/
│ └── config.yaml
│
├── data/
│ ├── raw/
│ ├── processed/
│ └── benchmark/
│
├── src/
│ ├── data/
│ │ ├── loader.py
│ │ ├── selector.py
│ │ └── chunker.py
│ │
│ ├── embeddings/
│ │ └── embedder.py
│ │
│ ├── vectorstore/
│ │ └── chroma_store.py
│ │
│ ├── retrieval/
│ │ ├── search.py
│ │ └── threshold.py
│ │
│ ├── evaluation/
│ │ ├── benchmark.py
│ │ └── metrics.py
│ │
│ └── rag/
│ └── pipeline.py
│
├── scripts/
│ ├── download_dataset.py
│ ├── build_chunks.py
│ ├── build_embeddings.py
│ ├── build_vector_db.py
│ └── evaluate.py
│
├── tests/
│
└── artifacts/
├── chunk_statistics.json
├── embedding_statistics.json
├── threshold_analysis.json
└── benchmark_results.json
