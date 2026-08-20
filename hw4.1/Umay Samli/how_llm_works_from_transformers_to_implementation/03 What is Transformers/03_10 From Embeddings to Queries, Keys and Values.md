Self-attention creates three different representations of each token by multiplying the input matrix $X$ by three trainable weight matrices:

$$Q=XW_Q,\qquad K=XW_K,\qquad V=XW_V$$

- **Query:** what this token is looking for.
- **Key:** what this token can be matched on.
- **Value:** the information this token contributes if selected.

For an input matrix of shape `(5, 8)` and projection matrices of shape `(8, 4)`, each of $Q$, $K$, and $V$ has shape `(5, 4)`. All tokens are projected in parallel.

To measure relationships, the model computes $QK^T$. The result has shape `(5, 5)`, containing one score for every query-token/key-token pair. Softmax turns each row into weights that sum to one. Multiplying those weights by $V$ produces the context vectors.

The matrices $W_Q$, $W_K$, and $W_V$ start with arbitrary values and are learned through backpropagation. Training teaches them which token relationships and information are useful for the model’s objective.
