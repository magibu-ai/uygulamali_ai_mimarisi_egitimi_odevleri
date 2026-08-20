After [[03_03 Tokenization|tokenization]] and [[03_05 Word Embedding|embedding]], token vectors enter the **Transformer block**, the main processing unit of the model.

Its two major computational sublayers are:

- **Multi-head self-attention:** lets every token collect relevant information from other tokens.
- **Feed-forward network:** independently transforms the representation of every token after attention has mixed information across the sequence.

Layer normalization keeps activation scales stable, shortcut or residual connections preserve information and gradient flow, and dropout reduces overfitting. A common pre-normalization flow is:

1. Normalize the input.
2. Apply multi-head attention and dropout.
3. Add the original input through a residual connection.
4. Normalize again.
5. Apply the feed-forward network and dropout.
6. Add another residual connection.

One block refines the token representations; stacking many identical blocks lets the model build progressively richer contextual and abstract features.
