**Byte Pair Encoding (BPE)** is a subword-tokenization algorithm originally developed for compression. It builds a vocabulary from the training corpus instead of requiring humans to decide where every word should be split.

The simplified process is:

1. Add an end-of-word marker such as `</w>` so the same letters at different word positions can be distinguished.
2. Split every word into individual characters.
3. Count adjacent token pairs, weighted by how often each word occurs.
4. Merge the most frequent pair into a new token.
5. Recount and repeat until the chosen vocabulary size is reached.

For example, if `es` occurs most frequently, BPE merges `e` + `s` into `es`. A later iteration might merge `es` + `t` into `est`. The final vocabulary contains a mixture of characters, common subwords, suffixes, and complete frequent words.

Each vocabulary item receives a token ID. GPT-2, for example, uses 50,000 merges and has 50,257 tokens. If a word is unfamiliar, BPE falls back to smaller known pieces, so it can still encode misspellings, new words, and foreign terms. The token IDs are labels only; [[03_05 Word Embedding|embeddings]] turn them into meaningful vectors.
