"""A tiny Byte-Pair Encoding (BPE) tokenizer for Turkish place names.

Drop-in replacement for CharTokenizer. Same interface, different guts:
CharTokenizer gives every character its own id; this one *learns* which
character groups deserve to be a single token by repeatedly merging the
most frequent adjacent pair -- the classic BPE training loop.

The newline "\n" separates names and doubles as the EOS token. It is never
merged into anything, so it always stays a hard boundary between names.

Usage:
    tok = BPETokenizer.from_file("../data/temiz_isimler.txt", vocab_size=300)
    ids = tok.encode("yesilkoy")      # -> [..]
    tok.decode(ids)                   # -> "yesilkoy"
    tok.eos_id                        # id of "\n"

Save / load (same shape CharTokenizer uses, so train.py needs no changes):
    torch.save({"chars": tok.chars, ...})
    tok = BPETokenizer(ckpt["chars"])
"""

from collections import defaultdict

NEWLINE = "\n"


class BPETokenizer:
    # ---------------------------------------------------------------- init
    def __init__(self, state: dict):
        """state = {"vocab": [token, ...], "merges": [[a, b], ...]}

        vocab  -- every token string, position = its id
        merges -- learned merge rules, IN ORDER (order matters at encode time)
        """
        self.vocab = list(state["vocab"])
        self.merges = [tuple(m) for m in state["merges"]]

        self.stoi = {t: i for i, t in enumerate(self.vocab)}   # token -> id
        self.itos = {i: t for i, t in enumerate(self.vocab)}   # id -> token
        self.vocab_size = len(self.vocab)

        # Merge rules as a dict for fast lookup, plus their priority (order).
        self.ranks = {pair: i for i, pair in enumerate(self.merges)}

        self.newline_id = self.stoi[NEWLINE]
        self.eos_id = self.newline_id

    @property
    def chars(self) -> dict:
        """Everything needed to rebuild this tokenizer.

        Named `chars` on purpose: train.py saves `tokenizer.chars` into the
        checkpoint and generate.py rebuilds with `Tokenizer(ckpt["chars"])`.
        Keeping the name means those scripts work untouched.
        """
        return {"vocab": self.vocab, "merges": [list(m) for m in self.merges]}

    # ------------------------------------------------------------ training
    @classmethod
    def from_file(cls, path: str, vocab_size: int = 300) -> "BPETokenizer":
        text = open(path, encoding="utf-8").read()
        if NEWLINE not in text:
            text += NEWLINE
        return cls.train(text, vocab_size)

    @classmethod
    def train(cls, text: str, vocab_size: int = 300) -> "BPETokenizer":
        # -- 1. Pre-tokenization -------------------------------------------
        # Each line is one name. Names are our "words"; BPE never merges
        # across a newline, so nothing bleeds from one name into the next.
        word_freqs = defaultdict(int)
        for line in text.split(NEWLINE):
            if line:
                word_freqs[line] += 1

        # -- 2. Base vocabulary --------------------------------------------
        # Every character that appears, plus the newline.
        alphabet = sorted({c for w in word_freqs for c in w})
        vocab = [NEWLINE] + alphabet          # newline first -> id 0

        # -- 3. Split every word into characters ---------------------------
        splits = {w: list(w) for w in word_freqs}

        merges = []

        # -- 4. The BPE loop -----------------------------------------------
        while len(vocab) < vocab_size:
            pair_freqs = cls._pair_freqs(splits, word_freqs)
            if not pair_freqs:
                break                          # nothing left to merge

            # Most frequent pair wins. Ties broken alphabetically so that
            # training the same file twice gives the exact same tokenizer.
            best = max(pair_freqs, key=lambda p: (pair_freqs[p], p))

            splits = cls._merge_pair(*best, splits, word_freqs)
            merges.append(best)
            vocab.append(best[0] + best[1])

        return cls({"vocab": vocab, "merges": merges})

    @staticmethod
    def _pair_freqs(splits, word_freqs):
        """Count every adjacent pair, weighted by how often its word occurs."""
        freqs = defaultdict(int)
        for word, freq in word_freqs.items():
            split = splits[word]
            for i in range(len(split) - 1):
                freqs[(split[i], split[i + 1])] += freq
        return freqs

    @staticmethod
    def _merge_pair(a, b, splits, word_freqs):
        """Apply one merge rule everywhere in the corpus."""
        ab = a + b
        for word in word_freqs:
            split = splits[word]
            if len(split) == 1:
                continue
            i = 0
            while i < len(split) - 1:
                if split[i] == a and split[i + 1] == b:
                    split = split[:i] + [ab] + split[i + 2:]
                else:
                    i += 1
            splits[word] = split
        return splits

    # ------------------------------------------------------------ encoding
    def _tokenize_word(self, word: str) -> list[str]:
        """Split one word into characters, then replay the merge rules.

        We always apply the *highest-priority* (earliest-learned) merge
        available, which is what makes encoding deterministic.
        """
        if not word:
            return []
        split = list(word)
        while len(split) > 1:
            pairs = [(split[i], split[i + 1]) for i in range(len(split) - 1)]
            candidates = [p for p in pairs if p in self.ranks]
            if not candidates:
                break
            best = min(candidates, key=lambda p: self.ranks[p])
            a, b = best
            i = 0
            while i < len(split) - 1:
                if split[i] == a and split[i + 1] == b:
                    split = split[:i] + [a + b] + split[i + 2:]
                else:
                    i += 1
        return split

    def encode(self, s: str) -> list[int]:
        """Encode text. Newlines are kept as their own token."""
        ids = []
        parts = s.split(NEWLINE)
        for i, part in enumerate(parts):
            if i > 0:
                ids.append(self.newline_id)
            for tok in self._tokenize_word(part):
                ids.append(self.stoi[tok])
            # Unknown characters cannot happen here: the base vocabulary
            # holds every character of the training corpus.
        return ids

    def decode(self, ids: list[int]) -> str:
        return "".join(self.itos[i] for i in ids)
