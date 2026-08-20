# Train Transformer — GPT From Scratch

> [!summary] Core idea
> The final demo combines tokenization, embeddings, attention, neural-network layers, backpropagation, and sampling into a decoder-only language model implemented without an ML library.

## Preparing training data

The program trains BPE on a small story corpus, maps the resulting tokens to IDs, and creates overlapping sequences. Each target sequence is the input shifted one position to the left:

**Input:** token₁, token₂, token₃  
**Target:** token₂, token₃, token₄

This teaches next-token prediction at every position.

## Model architecture

The miniature GPT uses token and positional embeddings followed by configurable Transformer blocks:

**Layer norm → multi-head causal self-attention → residual connection → layer norm → feed-forward network with ReLU → residual connection**

A final layer normalization and linear vocabulary head produce logits, and softmax converts them to next-token probabilities.

The default educational dimensions are deliberately small:

| Setting | Value |
|---|---:|
| Context length | 32 |
| Training sequence length | 16 |
| Embedding dimension | 32 |
| Attention heads | 2 |
| Feed-forward dimension | 128 |
| Transformer layers | Configurable |

The implementation stores weights in typed arrays and manually calculates matrix operations, scaled attention, causal masks, layer normalization, residual paths, and their gradients.

## Training

Weights use Xavier initialization to keep early activations stable. Cross-entropy measures the negative log-probability assigned to the correct next token. Backpropagation sends gradients from the vocabulary head through every block and into token and positional embeddings.

Adam updates the parameters using moving averages of gradients and squared gradients. Worker threads calculate gradients on different data partitions, after which the main process combines them and performs one update.

## Generating text

Generation repeatedly predicts and appends one token. **Temperature** controls randomness, while **top-p sampling** keeps the smallest high-probability set whose cumulative probability reaches the chosen threshold, then samples within it.

As training loss falls, generated samples move from random fragments toward patterns found in the training stories. The small model demonstrates the entire GPT pipeline, not the capabilities or general knowledge of a production LLM.
