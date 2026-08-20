# Byte-Level BPE Tokenizer from Wikipedia

A minimal, end-to-end pipeline that **scrapes text from Wikipedia**, trains a
**byte-level Byte-Pair Encoding (BPE)** tokenizer on it, and publishes the result
to the Hugging Face Hub.

> Trained tokenizer: [`gorkemergune/my-tokenizer`](https://huggingface.co/gorkemergune/my-tokenizer)

## Overview

| Step | File | What it does |
|---|---|---|
| 1. Scrape | [`scraper.py`](scraper.py) | Downloads a Wikipedia article as plain text into `text.txt` |
| 2. Train & push | [`script.py`](script.py) | Trains a byte-level BPE tokenizer on `text.txt` and pushes it to the Hub |

## Requirements

- Python 3.10+
- Dependencies (only needed for training):

```bash
pip install tokenizers transformers
```

`scraper.py` uses only the Python standard library — no extra packages needed.

## Usage

### 1. Scrape the source text

Set the `URL` you want inside [`scraper.py`](scraper.py), then run:

```bash
python scraper.py
```

This writes the article's plain text to `text.txt`. It uses the Wikipedia API's
`extracts` endpoint, so the output is clean text (no HTML, no reference markup).

### 2. Train the tokenizer and push to the Hub

Edit `REPO_ID` in [`script.py`](script.py) to your own Hugging Face repo, log in,
then run:

```bash
huggingface-cli login   # needed for push_to_hub
python script.py
```

This will:

1. Train a byte-level BPE tokenizer (vocab size 2048) on `text.txt`.
2. Save it locally to `my-tokenizer/`.
3. Push it to your Hugging Face repo.
4. Reload it via `AutoTokenizer` and print a sample encode/decode.

## Configuration

Key settings in [`script.py`](script.py):

| Variable | Default | Description |
|---|---|---|
| `TEXT_FILE` | `text.txt` | Training corpus produced by the scraper |
| `REPO_ID` | `gorkemergune/my-tokenizer` | Target Hugging Face repository |
| `VOCAB_SIZE` | `2 ** 11` (2048) | Final vocabulary size |
| `SPECIAL_TOKENS` | `<unk> <pad> <bos> <eos>` | Reserved special tokens |

## Load the trained tokenizer

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("gorkemergune/my-tokenizer")
ids = tokenizer.encode("Hello! This is a very small tokenizer example.")
print(tokenizer.convert_ids_to_tokens(ids))
print(tokenizer.decode(ids))
```

## Notes

- The tokenizer is a **learning demo** trained on a single Wikipedia article, so its
  merges are biased toward that article's domain.
- Being byte-level, it can encode any UTF-8 text without `<unk>` tokens despite the
  small vocabulary.

## License

MIT
