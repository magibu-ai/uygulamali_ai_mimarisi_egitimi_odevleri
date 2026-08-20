A feed-forward network treats inputs independently and has no built-in memory of word order or context. Language requires both: the meaning of a word often depends on words that appeared much earlier.

RNNs addressed this by processing tokens sequentially and passing a hidden state forward. However, their fixed-size state becomes an information bottleneck, long-range information can fade, and sequential computation prevents efficient parallel training. LSTMs improve memory with gates but do not fully remove these limitations.

Attention was first added to encoder-decoder RNNs for tasks such as translation. Instead of forcing the encoder to compress an entire sentence into one vector, the decoder compares its current state with every encoder state. A softmax turns these relevance scores into weights, and a weighted sum creates a context vector focused on the most useful source words.

This gives the model direct access to any position rather than requiring information to travel through every intermediate recurrent step. Transformers take the next step: they remove recurrence and make attention the central operation. [[03_08 Self Attention Mechanism|Self-attention]] applies the same idea inside a single sequence.
