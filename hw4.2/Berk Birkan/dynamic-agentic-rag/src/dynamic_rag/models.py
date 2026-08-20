"""Framework-independent domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    text: str
    source: str
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    parent_id: str
    text: str
    source: str
    title: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    similarity: float


@dataclass(frozen=True)
class RagAnswer:
    text: str
    answered: bool
    hits: list[SearchHit]
    trace: list[str] = field(default_factory=list)
