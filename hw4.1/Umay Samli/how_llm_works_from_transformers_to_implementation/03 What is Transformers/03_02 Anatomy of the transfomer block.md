The Transformer architecture was introduced in the 2017 paper [Attention Is All You Need](https://arxiv.org/abs/1706.03762). Its main innovation is **self-attention**, which replaced recurrent models such as RNNs, LSTMs, and GRUs for many language tasks.

The original Transformer has two sides:

- **Encoder:** reads and understands an input sequence. BERT is an encoder-only model.
- **Decoder:** generates an output sequence one token at a time. GPT is a decoder-only model.

A decoder-only LLM can be understood in three stages:

1. **Input:** [[03_03 Tokenization|tokenization]] converts text into token IDs. Token embeddings give those IDs meaning, while positional embeddings add information about order.
2. **Processing:** one or more Transformer blocks apply multi-head attention, feed-forward networks, layer normalization, dropout, and shortcut connections.
3. **Output:** a linear layer produces one score, or logit, for every token in the vocabulary. Softmax converts those scores into probabilities for the next token.

Transformers are effective because attention captures relationships between distant tokens, tokens can be processed in parallel during training, and the same block can be stacked repeatedly to create larger models.
