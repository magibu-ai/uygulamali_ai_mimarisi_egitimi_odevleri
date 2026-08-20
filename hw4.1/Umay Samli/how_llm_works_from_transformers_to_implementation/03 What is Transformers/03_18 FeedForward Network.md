After attention mixes information **between tokens**, the **feed-forward network (FFN)** transforms each token **independently**. The same weights are reused for every token and every example, so all token vectors can be processed in parallel.

A Transformer FFN usually contains two linear layers with a nonlinear activation in between:

$$\operatorname{FFN}(x)=W_2\,\operatorname{GELU}(W_1x+b_1)+b_2$$

The first layer expands the model dimension to a larger hidden dimension, often about four times wider. GELU introduces nonlinearity, and the second layer projects the result back to the original model dimension so it can be added to the residual path. Dropout is commonly applied for regularization.

Attention decides which information each token should gather from the sequence. The FFN then performs richer feature extraction and transformation on that gathered information. Together, these two sublayers give each Transformer block both token-to-token communication and per-token computation.
