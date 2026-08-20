# Introduction to Large Language Models

> [!summary] Core idea
> A Large Language Model is fundamentally a **token predictor**. Given all previous tokens as context, it assigns a probability to every possible next token.

A [[03_03 Tokenization|token]] is not necessarily a complete word or a single letter. Depending on the tokenizer, it may be a word, part of a word, punctuation, or another small text unit.

## How an LLM generates text

The model repeats the same cycle:

**Context → predict probabilities → choose a token → append it → repeat**

After receiving a conversation as input, the model predicts the next token. That token becomes part of the context used for the following prediction. Repeating this process allows the model to generate sentences, paragraphs, and complete conversations.

LLMs learn these predictions with artificial neural networks trained on enormous text datasets. During training, the network discovers patterns involving grammar, meaning, style, facts, and relationships between words.

## A probabilistic engine

There is usually more than one possible continuation. The model ranks the alternatives instead of finding one permanently “correct” answer.

### Turkish example

Input: **Anası mezar dik[…]**

| Possible token | Result | Example probability |
|---|---|---:|
| miş | dikmiş | 90% |
| er | diker | 5% |
| ar | dikar | 3% |
| mek | dikmek | 2% |

### English example

Input: **What the hell is wrong with […]**

| Possible token | Continuation | Example probability |
|---|---|---:|
| you | with you | 90% |
| me | with me | 5% |
| us | with us | 3% |
| them | with them | 2% |

> [!note]
> These probabilities are illustrative. The real distribution changes with the model, tokenizer, preceding context, and generation settings.

## Why is it called “large”?

“Large” mainly refers to the model’s enormous number of learned parameters, as well as the data and computation used for training.

[Scaling laws](https://arxiv.org/abs/2001.08361) show that model performance tends to improve predictably as model size, dataset size, and training compute increase. At sufficient scale, models can also display capabilities that are weak or absent in smaller models, such as multilingual understanding, arithmetic reasoning, summarization, and code generation.

The Transformer architecture makes this scaling practical by processing tokens in parallel and modeling both nearby context and long-range relationships.
