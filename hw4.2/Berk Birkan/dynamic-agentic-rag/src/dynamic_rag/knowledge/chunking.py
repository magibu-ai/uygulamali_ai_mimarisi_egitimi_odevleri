"""Paragraph-aware dynamic chunking with bounded overlap."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

from dynamic_rag.models import Chunk, Document


class MixedChunker:
    def __init__(self, token_count: Callable[[str], int], *, target_tokens: int = 384, overlap_tokens: int = 48):
        if not 0 <= overlap_tokens < target_tokens:
            raise ValueError("overlap_tokens must satisfy 0 <= overlap < target")
        self.token_count = token_count
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def _units(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        units = []
        for paragraph in paragraphs:
            if self.token_count(paragraph) <= self.target_tokens:
                units.append(paragraph)
            else:
                units.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip())
        return units

    def split(self, documents: list[Document]) -> list[Chunk]:
        output = []
        for document in documents:
            parent_id = hashlib.sha256(f"{document.source}\0{document.text}".encode()).hexdigest()[:20]
            current: list[str] = []
            for unit in self._units(document.text):
                candidate = "\n\n".join(current + [unit])
                if current and self.token_count(candidate) > self.target_tokens:
                    self._append(output, document, parent_id, current)
                    overlap = []
                    for prior in reversed(current):
                        if self.token_count("\n\n".join([prior] + overlap)) > self.overlap_tokens:
                            break
                        overlap.insert(0, prior)
                    current = overlap
                    if current and self.token_count("\n\n".join(current + [unit])) > self.target_tokens:
                        current = []
                if self.token_count(unit) > self.target_tokens:
                    words = unit.split()
                    while words:
                        take = []
                        while words and self.token_count(" ".join(take + [words[0]])) <= self.target_tokens:
                            take.append(words.pop(0))
                        if not take:
                            take.append(words.pop(0))
                        if take:
                            if current:
                                self._append(output, document, parent_id, current)
                                current = []
                            self._append(output, document, parent_id, [" ".join(take)])
                    continue
                current.append(unit)
            if current:
                self._append(output, document, parent_id, current)
        return output

    def _append(self, output: list[Chunk], document: Document, parent_id: str, units: list[str]) -> None:
        text = "\n\n".join(units).strip()
        if not text:
            return
        index = sum(chunk.parent_id == parent_id for chunk in output)
        chunk_id = hashlib.sha256(f"{parent_id}\0{index}\0{text}".encode()).hexdigest()[:24]
        output.append(Chunk(chunk_id, parent_id, text, document.source, document.title, index, document.metadata))
