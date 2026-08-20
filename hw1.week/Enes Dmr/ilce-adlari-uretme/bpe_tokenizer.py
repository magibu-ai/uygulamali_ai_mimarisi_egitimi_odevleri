import json

class BPETokenizer:
    def __init__(self):
        self.merges = {}                          # (id1, id2) -> new_id
        self.vocab = {i: bytes([i]) for i in range(256)}
        self.newline_id = 10                       # '\n' byte kodu, hep tek token kalır
        self.eos_id = self.newline_id

    def _stats(self, ids):
        counts = {}
        for a, b in zip(ids, ids[1:]):
            if a == self.eos_id or b == self.eos_id:
                continue          # isim/ilçe ayracını asla başka byte ile birleştirme
            counts[(a, b)] = counts.get((a, b), 0) + 1
        return counts

    def _merge(self, ids, pair, new_id):
        out, i = [], 0
        while i < len(ids):
            if i < len(ids) - 1 and (ids[i], ids[i + 1]) == pair:
                out.append(new_id); i += 2
            else:
                out.append(ids[i]); i += 1
        return out

    def train(self, text, vocab_size, verbose=False):
        ids = list(text.encode("utf-8"))
        for i in range(vocab_size - 256):
            stats = self._stats(ids)
            if not stats:
                break
            pair = max(stats, key=stats.get)
            new_id = 256 + i
            ids = self._merge(ids, pair, new_id)
            self.merges[pair] = new_id
            self.vocab[new_id] = self.vocab[pair[0]] + self.vocab[pair[1]]
            if verbose:
                print(f"merge {i+1}: {pair} -> {new_id} ({self.vocab[new_id]})")
        self.vocab_size = len(self.vocab)

    def encode(self, text):
        ids = list(text.encode("utf-8"))
        while True:
            pairs = set(zip(ids, ids[1:]))
            candidates = [p for p in pairs if p in self.merges]
            if not candidates:
                break
            pair = min(candidates, key=lambda p: self.merges[p])
            ids = self._merge(ids, pair, self.merges[pair])
        return ids

    def decode(self, ids):
        b = b"".join(self.vocab[i] for i in ids)
        return b.decode("utf-8", errors="replace")

    @classmethod
    def from_file(cls, path, vocab_size=300):
        text = open(path, encoding="utf-8").read()
        if "\n" not in text:
            text += "\n"
        tok = cls()
        tok.train(text, vocab_size, verbose=True)
        return tok