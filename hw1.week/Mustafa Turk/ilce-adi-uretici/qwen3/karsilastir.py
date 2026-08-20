"""Compare the character tokenizer against the BPE tokenizer, fairly.

Run:  python karsilastir.py

Why this script exists: you cannot compare the two models' losses directly.
Loss is measured per token, and a BPE token is not a character. A model
choosing among 300 tokens has a harder job than one choosing among 30
(baseline ln(300)=5.70 vs ln(30)=3.40), so BPE *looks* worse while actually
being better. The fair metric is bits-per-character: normalise the loss by
how many characters each token carries.

Trains both models from scratch, so it takes a few minutes.
"""

import math
import os

import torch

from bpe_tokenizer import BPETokenizer
from config import ModelConfig
from model import TinyQwen
from tokenizer import CharTokenizer

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "temiz_isimler.txt")
STEPS = 3000
BATCH_SIZE = 64
BLOCK_SIZE = 16
LEARNING_RATE = 3e-3
VOCAB_SIZE = 300
SEED = 1337


def egit(tokenizer, etiket):
    """Train one model and return (final_loss, n_tokens, n_params)."""
    torch.manual_seed(SEED)
    text = open(DATA_FILE, encoding="utf-8").read()
    data = torch.tensor(tokenizer.encode(text), dtype=torch.long)

    cfg = ModelConfig(vocab_size=tokenizer.vocab_size)
    model = TinyQwen(cfg)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    print(f"\n[{etiket}] vocab={tokenizer.vocab_size}  params={n_params:,}  "
          f"tokens={len(data):,}")

    losses = []
    for step in range(1, STEPS + 1):
        ix = torch.randint(len(data) - BLOCK_SIZE - 1, (BATCH_SIZE,))
        x = torch.stack([data[i:i + BLOCK_SIZE] for i in ix])
        y = torch.stack([data[i + 1:i + 1 + BLOCK_SIZE] for i in ix])
        _, loss = model(x, y)
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step > STEPS - 200:            # average the last 200 steps
            losses.append(loss.item())
        if step % 500 == 0:
            print(f"  step {step:5d}  loss {loss.item():.4f}")

    return sum(losses) / len(losses), len(data), n_params


def main():
    text = open(DATA_FILE, encoding="utf-8").read()
    n_chars = len(text)

    ch = CharTokenizer.from_file(DATA_FILE)
    bpe = BPETokenizer.from_file(DATA_FILE, vocab_size=VOCAB_SIZE)

    c_loss, c_tok, c_par = egit(ch, "CHAR")
    b_loss, b_tok, b_par = egit(bpe, "BPE")

    # bits per character = loss_per_token * tokens_per_char / ln(2)
    def bpc(loss, ntok):
        return loss * ntok / n_chars / math.log(2)

    print("\n" + "=" * 58)
    print("%-24s %-15s %-15s" % ("", "Char", "BPE"))
    print("-" * 58)
    print("%-24s %-15d %-15d" % ("vocab_size", ch.vocab_size, bpe.vocab_size))
    print("%-24s %-15s %-15s" % ("parametre", f"{c_par:,}", f"{b_par:,}"))
    print("%-24s %-15s %-15s" % ("toplam token", f"{c_tok:,}", f"{b_tok:,}"))
    print("%-24s %-15.3f %-15.3f" % ("loss (nats/token)", c_loss, b_loss))
    print("%-24s %-15.3f %-15.3f" % ("baseline (ln vocab)",
                                     math.log(ch.vocab_size), math.log(bpe.vocab_size)))
    print("-" * 58)
    print("ADİL KARŞILAŞTIRMA (karakter başına normalize)")
    print("%-24s %-15.3f %-15.3f" % ("baseline BPC",
                                     bpc(math.log(ch.vocab_size), c_tok),
                                     bpc(math.log(bpe.vocab_size), b_tok)))
    print("%-24s %-15.3f %-15.3f" % ("model BPC", bpc(c_loss, c_tok), bpc(b_loss, b_tok)))
    print("=" * 58)
    fark = (bpc(c_loss, c_tok) - bpc(b_loss, b_tok)) / bpc(c_loss, c_tok) * 100
    print(f"BPE karakter başına %{fark:.1f} daha iyi")


if __name__ == "__main__":
    main()
