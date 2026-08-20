"""Explicit, configurable tokenizer used for chunk-size measurement.

The chunker measures chunk size in *tokens*, not characters. The tokenizer is
defined explicitly in ``configs/config.yaml`` (``chunking.tokenizer``) and
documented, so chunk sizes are reproducible and auditable.

Currently the only backend is ``tiktoken`` (OpenAI's byte-level BPE). This is a
lightweight, deterministic, offline-cacheable tokenizer. It is used solely to
*measure* sizes while chunking; the embedding model chosen in Phase 3 has its
own tokenizer and is independent of this one.
"""
from __future__ import annotations

from typing import Any


class Tokenizer:
    """Thin wrapper exposing ``encode`` / ``decode`` / ``count``."""

    def __init__(self, backend: str, encoding: str):
        self.backend = backend
        self.encoding_name = encoding
        if backend != "tiktoken":
            raise ValueError(f"Unsupported tokenizer backend: {backend!r}")
        import tiktoken  # imported lazily so the package is only needed here

        self._enc = tiktoken.get_encoding(encoding)

    def encode(self, text: str) -> list[int]:
        return self._enc.encode(text)

    def decode(self, ids: list[int]) -> str:
        return self._enc.decode(ids)

    def count(self, text: str) -> int:
        return len(self._enc.encode(text))


def get_tokenizer(config: dict[str, Any]) -> Tokenizer:
    """Build the tokenizer described by ``chunking.tokenizer`` in the config."""
    tok_cfg = config["chunking"]["tokenizer"]
    return Tokenizer(backend=tok_cfg["backend"], encoding=tok_cfg["encoding"])
