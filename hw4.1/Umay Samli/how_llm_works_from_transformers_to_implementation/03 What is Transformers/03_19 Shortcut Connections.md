**Shortcut connections**, also called **residual connections**, add a sublayer’s input directly to its output:

$$y=x+F(x)$$

The function $F$ may be multi-head attention or a feed-forward network. The identity path preserves the original representation while the sublayer learns a useful change to it.

Residual connections are essential in deep Transformers because gradients can flow directly through the addition instead of passing through every nonlinear transformation. This reduces vanishing gradients, gives early layers a stronger learning signal, and allows many Transformer blocks to be stacked reliably.

They also make optimization easier: a sublayer can learn a small refinement, or even approximate zero when no change is useful, rather than having to reconstruct the complete representation. The resulting loss landscape tends to be smoother.

Inside each Transformer block, there is normally one residual connection around multi-head attention and another around the feed-forward network. Layer normalization and dropout work with these paths to keep deep training stable.
