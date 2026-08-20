The complete self-attention pipeline is:

1. Convert tokens into an input embedding matrix $X$.
2. Use learned projections to create $Q=XW_Q$, $K=XW_K$, and $V=XW_V$.
3. Compute all query-key similarities with $QK^T$.
4. Divide by $\sqrt{d_k}$ to keep score variance stable.
5. For autoregressive models, mask future positions with $-\infty$.
6. Apply row-wise softmax to obtain attention weights.
7. Optionally apply dropout during training.
8. Multiply the weights by $V$ to produce context vectors.

In one expression:

$$C=\operatorname{softmax}\left(\frac{QK^T}{\sqrt{d_k}}+M\right)V$$

Here $M$ is the optional attention mask. The output $C$ has one contextual vector per token: each vector is a learned weighted mixture of the value vectors.

A single attention head produces only one attention pattern and may struggle to represent several interpretations or relationship types simultaneously. [[03_16 Intuition of Multi-Head Attention|Multi-head attention]] solves this by learning several attention views in parallel.
