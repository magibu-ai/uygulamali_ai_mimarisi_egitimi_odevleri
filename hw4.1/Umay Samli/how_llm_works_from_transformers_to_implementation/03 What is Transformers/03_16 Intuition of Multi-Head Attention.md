A single self-attention head creates one attention matrix, so it may focus on only one interpretation of an ambiguous sentence or average incompatible relationships together.

**Multi-head attention** runs several attention mechanisms in parallel. Each head has its own learned query, key, and value projections and can specialize in a different kind of relationship—for example, syntax, pronoun references, nearby context, or long-range semantic links.

If the model dimension is $d_{model}$ and there are $h$ heads, each head commonly uses:

$$d_{head}=\frac{d_{model}}{h}$$

Every head independently calculates scaled dot-product attention. Their context matrices are concatenated and passed through a final output projection:

$$\operatorname{MultiHead}(X)=\operatorname{Concat}(head_1,\ldots,head_h)W_O$$

Splitting the dimension keeps the combined output size and computational cost manageable, although each individual head has less representational capacity. The benefit is diversity: the final token vector combines several learned perspectives rather than relying on one attention pattern.
