Large Language Models learn a probability distribution for the next token. Repeating that prediction generates complete text, while increasing model size, data, and compute can produce powerful and sometimes emergent capabilities.

The Transformer pipeline is:

1. [[03_03 Tokenization|Tokenization]] converts text into IDs; BPE provides flexible subword units.
2. Token and positional embeddings convert IDs into vectors containing identity and order.
3. Self-attention projects those vectors into queries, keys, and values, computes scaled similarities, applies softmax, and blends values into contextual vectors.
4. Causal masks stop decoder models from seeing future tokens; padding masks hide artificial padding.
5. Multi-head attention learns several relationship types in parallel.
6. Feed-forward networks transform each token independently.
7. Layer normalization and residual connections stabilize deep stacks; dropout reduces overfitting.

Transformers outperform RNNs and CNNs at scale because they process training sequences in parallel, connect distant tokens directly, and reuse a uniform stackable block. Pretraining turns this architecture into a reusable foundation that can be fine-tuned for many tasks. Its major costs are quadratic attention for long sequences, high data and compute requirements, deployment expense, and learned bias.
