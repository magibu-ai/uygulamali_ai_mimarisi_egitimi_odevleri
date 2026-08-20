# ROADMAP.md

# Turkish Medical Vector Search & RAG

## Phase 0 — Project Specification & Setup

### Goals

- Understand the existing architecture.
- Confirm dataset, embedding model, vector database, and project structure.
- Establish reproducibility rules.
- Create project configuration and documentation.

### Tasks

- [ ] Inspect existing repository.
- [ ] Inspect existing architecture and source files.
- [ ] Confirm dataset.
- [ ] Confirm embedding model.
- [ ] Confirm ChromaDB configuration.
- [ ] Create/update `CLAUDE.md`.
- [ ] Create/update `ROADMAP.md`.
- [ ] Create/update `PROMPT.md`.
- [ ] Establish configuration system.
- [ ] Establish test infrastructure.

### Exit Criteria

- Repository structure is understood.
- Configuration is centralized.
- No implementation assumptions remain undocumented.

---

# Phase 1 — Dataset Acquisition

### Goals

Download and prepare the selected Hugging Face medical dataset.

### Tasks

- [ ] Load the dataset using Hugging Face Datasets.
- [ ] Inspect all available columns.
- [ ] Inspect missing values.
- [ ] Inspect document lengths.
- [ ] Identify URL/source/title fields.
- [ ] Decide the document selection strategy.
- [ ] Select between 100 and 1,000 documents.
- [ ] Use a fixed random seed if random selection is used.
- [ ] Save the selected document metadata.
- [ ] Generate dataset statistics.

### Validation

Verify:

- document count is between 100 and 1,000
- `text` exists
- source/URL information is available or a documented fallback exists
- selected documents contain meaningful text
- selection is reproducible

### Exit Criteria

A deterministic document collection exists and can be reproduced.

---

# Phase 2 — Chunking

### Goals

Convert selected articles into retrieval-friendly chunks.

### Strategy

Use a mixed strategy:

1. Paragraph-based splitting.
2. Maximum token limit.
3. Token-based fallback for oversized paragraphs.
4. Controlled overlap.

### Tasks

- [ ] Implement deterministic chunker.
- [ ] Preserve document metadata.
- [ ] Assign unique chunk IDs.
- [ ] Assign parent document IDs.
- [ ] Preserve source URL.
- [ ] Store chunk text.
- [ ] Record chunk statistics.
- [ ] Test edge cases.

### Validation

Measure:

- number of documents
- number of chunks
- minimum chunk length
- maximum chunk length
- mean chunk length
- median chunk length
- oversized chunk count
- empty chunk count

### Exit Criteria

Every selected document is represented by one or more valid chunks.

---

# Phase 3 — Embedding

### Goals

Generate vector representations for all chunks.

### Tasks

- [ ] Load the selected embedding model.
- [ ] Verify model output dimension.
- [ ] Generate embeddings in batches.
- [ ] Normalize embeddings if required by the retrieval implementation.
- [ ] Verify embedding count equals chunk count.
- [ ] Validate vector dimensions.
- [ ] Save embedding metadata.

### Validation

Verify:

- no missing vectors
- consistent dimensions
- deterministic pipeline configuration
- query and document embeddings use the same model

### Exit Criteria

Every chunk has a valid embedding vector.

---

# Phase 4 — ChromaDB

### Goals

Store and retrieve embedded chunks.

### Required Schema

- `id`
- `url`
- `chunk_text`
- `chunk_vector`

Recommended metadata:

- `title`
- `parent_id`
- `source`

### Tasks

- [ ] Initialize ChromaDB.
- [ ] Create collection.
- [ ] Insert documents.
- [ ] Insert embeddings.
- [ ] Insert metadata.
- [ ] Implement top-k similarity search.
- [ ] Return similarity scores.
- [ ] Verify persistence.

### Validation

- Insert a known chunk.
- Search using a related query.
- Verify the expected chunk appears.
- Verify similarity scores are available.
- Restart the application and verify persistence.

### Exit Criteria

The vector database can reliably retrieve relevant chunks.

---

# Phase 5 — Benchmark Dataset

### Goals

Create the official 30-question evaluation set.

### Structure

20 positive questions:

- answer exists directly in the selected documents
- expected source/chunk must be recorded

10 negative questions:

- answer does not exist in the selected documents
- expected source must be null

### Tasks

- [ ] Create benchmark schema.
- [ ] Select source chunks for positive questions.
- [ ] Write 20 positive questions.
- [ ] Verify every positive answer exists in the source chunk/document.
- [ ] Write 10 realistic negative questions.
- [ ] Verify negative answers are absent from the selected corpus.
- [ ] Freeze benchmark version.

### Exit Criteria

Exactly 30 valid benchmark questions exist.

---

# Phase 6 — Retrieval & Threshold

### Goals

Implement similarity search and determine a defensible threshold.

### Tasks

- [ ] Embed benchmark questions.
- [ ] Retrieve top-k chunks.
- [ ] Record top-1 score.
- [ ] Record top-k scores.
- [ ] Determine whether expected evidence was retrieved.
- [ ] Analyze positive score distribution.
- [ ] Analyze negative score distribution.
- [ ] Search for a threshold separating positive and negative queries.
- [ ] Evaluate candidate thresholds.
- [ ] Select the final threshold.
- [ ] Save threshold analysis.

### Important

Do not choose the threshold arbitrarily.

The threshold must be justified using benchmark results.

### Output

For every benchmark query record:

- question ID
- question
- type
- top-k results
- top similarity score
- threshold
- accepted/rejected
- expected evidence retrieved or not

### Exit Criteria

The retrieval system correctly demonstrates threshold-based rejection behavior.

---

# Phase 7 — RAG Answering Layer

### Goals

Add answer generation only after retrieval has been validated.

### Pipeline

Question
→ Query Embedding
→ Vector Search
→ Threshold Gate
→ Relevant Chunks
→ LLM Answer

If below threshold:

→ "Bu sorunun cevabı dokümanlarımda yer almamaktadır."

### Tasks

- [ ] Implement retrieval gate.
- [ ] Implement context construction.
- [ ] Implement LLM interface.
- [ ] Prevent LLM calls below threshold.
- [ ] Ensure answers are grounded in retrieved context.
- [ ] Test positive questions.
- [ ] Test negative questions.

### Exit Criteria

Negative questions never reach the answering layer when below threshold.

---

# Phase 8 — Evaluation & Documentation

### Goals

Produce final academic deliverables.

### Tasks

- [ ] Run complete benchmark.
- [ ] Generate evaluation report.
- [ ] Generate retrieval statistics.
- [ ] Generate threshold analysis.
- [ ] Document chunking strategy.
- [ ] Document embedding model and dimension.
- [ ] Document vector database.
- [ ] Document dataset selection.
- [ ] Document benchmark methodology.
- [ ] Document limitations.
- [ ] Complete README.md.
- [ ] Validate final repository.
- [ ] Prepare Hugging Face repository.

### Final Checklist

- [ ] 100–1,000 documents
- [ ] valid chunks
- [ ] valid embeddings
- [ ] ChromaDB operational
- [ ] 20 positive questions
- [ ] 10 negative questions
- [ ] cosine similarity
- [ ] threshold filtering
- [ ] negative questions rejected
- [ ] threshold analysis documented
- [ ] README complete
- [ ] reproducible pipeline
