Neural networks cannot process raw text, so a tokenizer splits it into **tokens** and assigns every token a numerical ID.

There are three common strategies:

- **Word-based:** one token per complete word. It is intuitive, but creates a huge vocabulary, treats related words such as “learn” and “learning” as unrelated, and cannot represent unseen or misspelled words.
- **Character-based:** one token per character. It needs only a small vocabulary, but creates very long sequences and gives the model units with little semantic meaning.
- **Subword-based:** frequent words may remain whole, while rarer words are divided into reusable parts. For example, “playground” can become “play” + “ground”.

Modern LLMs usually use subword tokenization because it balances vocabulary size, sequence length, and meaning. It can also represent a new word by combining known pieces instead of using an unknown-word token.

The remaining question is how to choose useful subwords. [[03_04 Byte Pair Encoding]] answers this with a data-driven algorithm that repeatedly merges common adjacent units.
