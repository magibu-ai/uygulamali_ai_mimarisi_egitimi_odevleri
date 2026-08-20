Matrix multiplication combines rows from the first matrix with columns from the second. If $A$ has shape `(m, n)` and $B$ has shape `(n, p)`, then:

$$AB\text{ has shape }(m,p)$$

The two inner dimensions must match. Each output entry is a dot product:

$$C_{ij}=\sum_k A_{ik}B_{kj}$$

This explains why an input embedding matrix of shape `(5, 8)` can be multiplied by a weight matrix of shape `(8, 4)` to produce `(5, 4)`: every eight-dimensional token vector is projected to four dimensions.

A **transpose** swaps rows and columns. If $K$ has shape `(5, 4)`, then $K^T$ has shape `(4, 5)`. Therefore $QK^T$ multiplies `(5, 4)` by `(4, 5)` and produces a `(5, 5)` attention-score matrix. Entry `(i, j)` measures the compatibility between token $i$’s query and token $j$’s key.
