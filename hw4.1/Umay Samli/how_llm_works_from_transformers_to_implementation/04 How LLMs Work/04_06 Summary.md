# How LLMs Work — Summary

The project builds an LLM concept by concept:

1. [[04_01 Simple Chat - Pattern Matching|Pattern matching]] shows that a convincing chat interface can be powered by fixed rules. Streaming output is separate from intelligence.
2. [[04_02 XOR Neural Net - Backpropagation|The XOR network]] replaces rules with learned weights. A hidden layer represents nonlinear patterns, and backpropagation finds parameters that reduce error.
3. [[04_03 Basic Tokenizer - BPE From Scratch|BPE tokenization]] converts text into reusable subword units by repeatedly merging frequent pairs.
4. [[04_04 Train Embeddings - Word2Vec Skip-Gram|Skip-gram]] turns tokens into vectors by pulling real context pairs together and pushing negative samples apart.
5. [[04_05 Train Transformer - GPT From Scratch|The miniature GPT]] combines embeddings, positional information, causal multi-head attention, feed-forward layers, normalization, residual connections, cross-entropy loss, backpropagation, and Adam optimization.

The complete learning loop is:

**Text → tokens → token IDs → embeddings → contextual Transformer representations → vocabulary probabilities → loss → gradients → updated weights**

During inference, training stops and the learned weights are reused:

**Prompt → tokenization → forward pass → temperature and top-p sampling → next token → repeat**

> [!important]
> An LLM does not contain a database of hand-written answers. Its behavior emerges from numerical parameters adjusted during training to make useful token predictions.

The repository’s tiny implementations use the same foundational ideas as larger systems, but production LLMs add vastly more parameters, data, compute, engineering, evaluation, and safety mechanisms.
