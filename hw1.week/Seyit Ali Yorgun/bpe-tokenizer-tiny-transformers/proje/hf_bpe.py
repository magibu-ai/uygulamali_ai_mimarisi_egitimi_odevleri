import os

from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders

EOS = "\n"
HERE = os.path.dirname(__file__)
DATA_FILE = os.path.join(HERE, "data", "mineraller.txt")
TOKENIZER_JSON = os.path.join(HERE, "tokenizer.json")


def train_hf_bpe(data_file: str = DATA_FILE, vocab_size: int = 500,
                 out_path: str = TOKENIZER_JSON) -> Tokenizer:
    """HF `tokenizers` ile BPE eğit, tokenizer.json kaydet."""
    lines = [l for l in open(data_file, encoding="utf-8").read().split("\n") if l]

    tok = Tokenizer(models.BPE(unk_token=None))
    # Boşluk pretokenizer: her satır tek "kelime" (korpusta boşluk yok). Merge'ler
    # kelime sınırını aşmaz -> EOS asla harflere yapışmaz.
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tok.decoder = decoders.BPEDecoder(suffix="")

    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=[EOS],          # EOS her zaman sözlükte, sabit id
        initial_alphabet=sorted({c for l in lines for c in l}),
        show_progress=False,
    )
    tok.train_from_iterator(lines, trainer=trainer)
    tok.save(out_path)
    return tok


class HFTokenizer:
    """single_letter_transformers arayüzüne saran adaptör.

    Modeller şunları bekler: encode(text)->ids, decode(ids)->text, vocab_size,
    newline_id, eos_id. "\n" ad ayıracı/EOS olarak stream'e elle eklenir.
    """

    def __init__(self, tok: Tokenizer):
        self.tok = tok
        self.eos_id = tok.token_to_id(EOS)
        self.newline_id = self.eos_id
        self.vocab_size = tok.get_vocab_size()

    @classmethod
    def load(cls, path: str = TOKENIZER_JSON) -> "HFTokenizer":
        return cls(Tokenizer.from_file(path))

    def encode(self, text: str) -> list[int]:
        """Metni token id'lerine çevir. Her satır (ad) sonuna EOS eklenir."""
        ids: list[int] = []
        for line in text.split(EOS):
            if not line:
                continue
            ids.extend(self.tok.encode(line).ids)
            ids.append(self.eos_id)
        return ids

    def decode(self, ids: list[int]) -> str:
        """id'leri metne çevir. EOS -> "\n". Diğerleri düz alt-dizge (byte-level yok)."""
        out = []
        for i in ids:
            t = self.tok.id_to_token(i)
            out.append(EOS if i == self.eos_id else t)
        return "".join(out)


if __name__ == "__main__":
    tok = train_hf_bpe()
    print(f"tokenizer.json kaydedildi -> {TOKENIZER_JSON}")
    print(f"sözlük boyutu = {tok.get_vocab_size()}")
    ad = HFTokenizer(tok)
    for name in ["hematit", "kalkopirit", "rodokrozit"]:
        ids = ad.encode(name)
        toks = [tok.id_to_token(i) for i in ids]
        print(f"{name!r:16} -> {toks}  ({len(ids)} token)  decode: {ad.decode(ids)!r}")
