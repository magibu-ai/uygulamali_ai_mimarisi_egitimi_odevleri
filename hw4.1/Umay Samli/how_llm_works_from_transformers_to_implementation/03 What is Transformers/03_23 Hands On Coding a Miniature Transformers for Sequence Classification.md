This section builds a small BERT-style encoder from scratch for positive/negative sentiment classification on the 50,000-review IMDb dataset.

The implementation pipeline is:

1. Tokenize reviews with GPT-2 BPE and add `[PAD]`, `[CLS]`, and `[SEP]` IDs.
2. Truncate or pad every input to 256 tokens and create a padding mask.
3. Sum token, learned positional, and segment embeddings, then apply normalization and dropout.
4. Implement bidirectional multi-head self-attention. Unlike GPT, it masks padding only—not future tokens.
5. Add a GELU feed-forward network, pre-layer normalization, and residual connections to form a reusable encoder block.
6. Stack the blocks into a BERT encoder.
7. Use the final `[CLS]` representation as a summary of the sequence and map it to two sentiment logits with a linear classifier.
8. Train with cross-entropy loss and AdamW; evaluate with dropout disabled and gradients turned off.

The miniature model uses 256-dimensional embeddings, a 1024-dimensional FFN, multiple layers and attention heads, and reports about 80.7% test accuracy. The exercise demonstrates how the conceptual components fit together, while also showing the limitations of a small model trained from scratch and restricted to 256-token inputs.
