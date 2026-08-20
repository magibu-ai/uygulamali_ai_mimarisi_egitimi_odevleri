# PROMPT.md

## Claude Code Execution Protocol

You are working on an academic Turkish medical vector search and RAG project.

The project is divided into phases in `ROADMAP.md`.

### Before Every Task

1. Read `CLAUDE.md`.
2. Read the relevant section of `ROADMAP.md`.
3. Inspect the current repository state.
4. Inspect existing implementations before creating new files.
5. Identify dependencies between the requested task and existing artifacts.

### Scope Rule

Implement only the requested phase.

Do not automatically continue to later phases.

If a later phase depends on the current implementation, document the dependency but do not implement it yet.

### Implementation Rules

- Prefer simple and maintainable implementations.
- Avoid unnecessary abstractions.
- Do not duplicate configuration.
- Do not hard-code values that belong in configuration.
- Do not fabricate data or results.
- Do not silently discard documents or chunks.
- Preserve source metadata.
- Make all data transformations reproducible.
- Use deterministic random seeds.
- Add tests for critical logic.

### Validation Rule

After implementation:

1. Run the relevant tests.
2. Run the relevant pipeline command.
3. Inspect generated output.
4. Check counts and dimensions.
5. Check for missing or malformed data.
6. Report validation results.

Do not claim success without actually running validation.

### Data Integrity Rule

Whenever a transformation occurs, verify:

- input count
- output count
- invalid records
- missing values
- metadata preservation

### Embedding Integrity

Verify:

- model name
- embedding dimension
- number of embeddings
- chunk/vector alignment

Never mix embeddings generated with different models.

### Vector Search Integrity

Every search result must expose:

- chunk ID
- similarity/distance score
- chunk text
- source metadata

The threshold decision must be made after retrieval.

### Benchmark Integrity

The benchmark must contain exactly:

- 20 positive questions
- 10 negative questions

Positive questions must have verifiable evidence in the selected corpus.

Negative questions must not have supporting evidence in the selected corpus.

Never modify the benchmark merely to improve scores.

### Threshold Integrity

Threshold selection must be evidence-based.

Evaluate candidate thresholds against the benchmark.

Record:

- positive score distribution
- negative score distribution
- false positives
- false negatives
- selected threshold

Do not choose a threshold only because it produces a desired result.

### Documentation

Every major architectural decision must be reflected in README.md.

README must explain:

1. Dataset
2. Document selection
3. Chunking strategy
4. Embedding model
5. Embedding dimension
6. ChromaDB
7. Retrieval method
8. Cosine similarity
9. Threshold selection
10. Benchmark methodology
11. Results
12. Limitations

### Git Discipline

After completing a phase:

- inspect `git diff`
- inspect `git status`
- ensure generated junk is ignored
- create a focused commit if requested

Never push automatically.

### Completion Report

At the end of every phase report:

#### Implemented

- ...

#### Files Changed

- ...

#### Validation

- ...

#### Metrics

- ...

#### Decisions

- ...

#### Known Issues

- ...

#### Next Phase

- ...

Do not start the next phase automatically.
