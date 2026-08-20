A token ID is only an arbitrary label; its numerical value says nothing about meaning. An **embedding layer** maps each token ID to a dense, learned vector.

Earlier representations have important limitations. One-hot vectors are extremely large and place every pair of words at the same distance. Bag-of-words representations count tokens but discard order, making “dog bites man” indistinguishable from “man bites dog”.

Embeddings use the idea that words appearing in similar contexts tend to have related meanings. Training positions related concepts near one another in a high-dimensional vector space. Modern LLM embedding sizes commonly range from hundreds to thousands of dimensions.

Transformer representations also become **contextual**: “bank” can acquire different representations in “river bank” and “investment bank”. Self-attention performs this contextualization; the initial embedding is only the starting representation.

Attention processes tokens in parallel and has no built-in knowledge of sequence order. Therefore the model adds a **positional embedding** to each token embedding. The final input vector is:

`input embedding = token embedding + positional embedding`

Simple integer positions can overwhelm token values, while binary positions change discontinuously. Sinusoidal or learned positional embeddings provide bounded, useful position signals, allowing identical tokens at different locations to be distinguished.
