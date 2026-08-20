Deep networks can suffer from unstable activation scales and exploding or vanishing gradients. **Layer normalization** makes the input to each Transformer sublayer more consistent, improving numerical stability and convergence.

For one token’s feature vector, it computes the mean and variance across that vector’s features and normalizes each value:

$$\hat{x}_i=\frac{x_i-\mu}{\sqrt{\sigma^2+\epsilon}}$$

The result has approximately zero mean and unit variance. Learned parameters then restore flexibility:

$$y_i=\gamma_i\hat{x}_i+\beta_i$$

Unlike batch normalization, layer normalization treats every example and token independently and does not depend on batch statistics. This makes it suitable for variable-length sequences, small batches, and one-token-at-a-time generation.

In a pre-normalization Transformer, layer normalization appears before multi-head attention and before the feed-forward network. It controls the scale entering each sublayer, while [[03_19 Shortcut Connections|residual connections]] provide a direct route for information and gradients.
