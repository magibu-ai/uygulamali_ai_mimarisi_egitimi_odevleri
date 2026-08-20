Ordinary self-attention can use information from every position. That would let a next-token model “cheat” during training by looking at the future token it is supposed to predict.

**Causal attention** prevents this information leak. A lower-triangular mask permits every token to attend only to itself and earlier positions. Before softmax, forbidden scores above the diagonal are replaced with negative infinity:

$$\text{masked scores}_{ij}=\begin{cases}
\text{score}_{ij} & j\le i\\
-\infty & j>i
\end{cases}$$

Because $e^{-\infty}=0$, future positions receive exactly zero probability after softmax. The first token can attend only to itself; the second can attend to the first two tokens; the final token can attend to the full preceding context. Every row still sums to one.

The mask must be applied **before** softmax. Zeroing probabilities afterward would make rows sum to less than one unless they were renormalized. Decoder-only models such as GPT use causal masking, while encoder models such as BERT generally use bidirectional attention and mask only padding tokens.
