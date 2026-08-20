Attention divides query-key dot products by $\sqrt{d_k}$ before softmax:

$$\operatorname{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)$$

The dot product adds $d_k$ element-wise products. If query and key components are independent with roughly unit variance, the dot product’s variance grows to approximately $d_k$. Larger key dimensions therefore produce increasingly large positive and negative scores.

Large score differences make softmax extremely sharp: one probability approaches 1 while the others approach 0. Softmax then enters a saturated region with tiny gradients, making learning slow and unstable.

Dividing by $\sqrt{d_k}$ returns the variance to approximately 1 and keeps the scores in a numerically useful range. The resulting attention distribution can remain selective without becoming prematurely one-hot, so gradients continue to flow during training.

This scaling does not change which key has the highest raw compatibility. It controls the magnitude and temperature of the distribution.
