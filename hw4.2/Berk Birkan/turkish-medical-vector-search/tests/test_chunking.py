from turkish_medical_vector_search.chunking.mixed import MixedChunker


class WhitespaceTokenizer:
    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.reverse: dict[int, str] = {}

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        del add_special_tokens
        ids = []
        for token in text.replace("\n", " ").split():
            if token not in self.vocab:
                token_id = len(self.vocab) + 1
                self.vocab[token] = token_id
                self.reverse[token_id] = token
            ids.append(self.vocab[token])
        return ids

    def decode(self, token_ids: list[int], *, skip_special_tokens: bool = True) -> str:
        del skip_special_tokens
        return " ".join(self.reverse[token_id] for token_id in token_ids)


def test_mixed_chunker_respects_limit_and_repeats_title() -> None:
    tokenizer = WhitespaceTokenizer()
    chunker = MixedChunker(tokenizer, target_tokens=30, overlap_tokens=5, min_chunk_tokens=8)
    text = "\n".join(
        [
            "Birinci paragraf " + " ".join(f"a{i}" for i in range(20)),
            "İkinci paragraf " + " ".join(f"b{i}" for i in range(20)),
        ]
    )

    chunks = chunker.chunk(title="Deri Sağlığı", text=text)

    assert len(chunks) >= 2
    assert all(chunk.chunk_text.startswith("Başlık: Deri Sağlığı") for chunk in chunks)
    assert all(chunk.token_count <= 30 for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_empty_article_returns_no_chunks() -> None:
    chunker = MixedChunker(
        WhitespaceTokenizer(), target_tokens=30, overlap_tokens=5, min_chunk_tokens=8
    )
    assert chunker.chunk(title="Boş", text="  \n ") == []
