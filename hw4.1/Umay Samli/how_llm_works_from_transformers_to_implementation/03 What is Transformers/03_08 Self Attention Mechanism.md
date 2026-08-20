**Self-attention** lets every token examine all tokens in the same sequence, including itself, and decide how relevant each one is. This differs from cross-attention, which connects two different sequences, such as a translated sentence and its source.

The mechanism transforms static input embeddings into context-aware vectors:

1. Project every input into a query, key, and value vector.
2. Compare each query with every key using dot products.
3. Scale the scores and pass each row through softmax to obtain attention weights.
4. Use those weights to calculate a weighted sum of the value vectors.

The complete operation is:

$$\operatorname{Attention}(Q,K,V)=\operatorname{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Queries express what a token is looking for, keys express what each token offers, and values contain the information to retrieve. The learned projection matrices allow these roles to differ even though they originate from the same embeddings.

The output for each token is a blend of information from the entire sequence. Consequently, a word’s new context vector represents what it means in this particular sentence rather than in isolation.
