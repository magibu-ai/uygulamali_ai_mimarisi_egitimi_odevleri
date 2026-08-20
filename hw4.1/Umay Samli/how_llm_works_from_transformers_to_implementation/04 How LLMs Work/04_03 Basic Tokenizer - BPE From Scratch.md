# Basic Tokenizer — BPE From Scratch

> [!summary] Core idea
> Byte Pair Encoding learns a reusable subword vocabulary by repeatedly merging the most frequent neighboring units in a training corpus.

This demo implements the concept introduced in [[03_04 Byte Pair Encoding]] and visualizes every merge.

## Training the tokenizer

The pipeline is:

1. **Pre-tokenize:** split text into words, individual spaces, and punctuation.
2. **Count unique pieces:** record how frequently each pre-token appears.
3. **Start with characters:** represent every pre-token as individual characters.
4. **Count adjacent pairs:** weight each pair by the frequency of its pre-token.
5. **Merge the most frequent pair:** replace every occurrence with one new token.
6. **Repeat:** stop at the merge limit or when no pairs remain.

For example, with “cat” appearing three times and “car” twice, the pair **c + a** has frequency five. The first merge creates **ca**; later merges may create **cat** and **car**.

## Why pre-tokenization matters

Merges are applied independently inside each pre-token. This prevents nonsensical tokens that cross boundaries, such as merging the end of “cat” with the following space or word.

Counting unique pre-tokens is also efficient. If “the” appears millions of times, its character sequence is stored once while its pair counts are weighted by its frequency.

## Using the trained tokenizer

To tokenize new text, the model performs the same pre-tokenization, splits each piece into characters, and replays the learned merge rules **in their original order**. Order matters because later tokens depend on earlier merges.

The result is a vocabulary containing characters, common subwords, punctuation, spaces, and frequent complete words. The demo reports the final token sequence and compression ratio, showing how learned merges shorten the character-level representation.
