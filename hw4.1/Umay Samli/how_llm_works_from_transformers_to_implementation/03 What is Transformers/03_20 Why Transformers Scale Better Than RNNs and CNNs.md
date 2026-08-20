Transformers scale more effectively than earlier sequence architectures for three main reasons.

**Parallel computation:** RNNs must process token $t$ after token $t-1$, creating a sequential bottleneck. Self-attention computes representations for all positions at once during training, making much better use of GPUs and distributed hardware.

**Direct global context:** In an RNN, information may travel through many recurrent steps; in a CNN, distant tokens require many layers or large kernels. Self-attention connects any pair of tokens in one layer, making long-range dependencies easier to learn.

**Uniform, stackable architecture:** The same Transformer block can be repeated and systematically widened or deepened. Layer normalization and residual connections stabilize large stacks, and attention adapts its connections to the input rather than using a fixed convolution pattern.

These properties lead to predictable improvements as parameters, training data, and compute increase. The main trade-off is that standard attention has quadratic time and memory cost in sequence length, discussed in [[03_22 Limitations and Challenges of Transformers]].
