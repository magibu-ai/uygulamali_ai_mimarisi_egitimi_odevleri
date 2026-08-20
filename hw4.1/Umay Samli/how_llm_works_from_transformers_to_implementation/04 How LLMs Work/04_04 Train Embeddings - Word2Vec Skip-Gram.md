# Train Embeddings — Word2Vec Skip-Gram

> [!summary] Core idea
> Skip-gram learns meaning from context: tokens used near similar tokens receive vectors that point in similar directions.

After [[04_03 Basic Tokenizer - BPE From Scratch|BPE tokenization]], the demo builds a vocabulary and creates training pairs from a sliding context window. In each pair, the **target token** is used to predict a nearby **context token**.

## Model and objective

The model contains two matrices:

- **Wᵢₙ:** input vectors; its rows become the final learned embeddings.
- **Wₒᵤₜ:** output vectors used while predicting context tokens.

For a real target-context pair, training increases their dot product and pulls their vectors closer. However, comparing the target with every token in the vocabulary would be expensive.

**Negative sampling** provides a cheaper alternative. For every real pair, the trainer samples several random tokens that were not the context and pushes those vectors apart. Tokens are sampled from a frequency distribution raised to the power **0.75**, balancing very common and rare tokens.

The loss encourages:

- **sigmoid(target · real context) → 1**
- **sigmoid(target · negative sample) → 0**

## Reading the learned space

After training, semantic relationships become geometric:

- **Cosine similarity** measures the angle between two vectors.
- Nearest-neighbor search finds tokens used in similar contexts.
- Vector arithmetic can model analogies such as **king − man + woman ≈ queen**.

The demo displays loss over time, query-token vectors, nearest neighbors, pairwise similarities, and analogy results.

> [!note]
> Embedding quality depends strongly on corpus size and diversity. This small educational corpus demonstrates the mechanism, but its relationships will be less reliable than embeddings trained on billions of tokens.
