"""Request and response contracts.

No model in this module has a field that can hold a credential. The provider key
travels in a request *header* only (see ``ehekim.api``), so it can never be
accidentally echoed by a response model, captured by request-body logging, or
written into a URL that ends up in an access log.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K,
    MAX_QUERY_CHARS,
    MAX_TOP_K,
)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    threshold: float = Field(default=DEFAULT_SIMILARITY_THRESHOLD, ge=0.0, le=1.0)


class AskRequest(SearchRequest):
    model_config = ConfigDict(extra="forbid")

    model_key: str | None = None
    include_reasoning: bool = False


class ChunkResult(BaseModel):
    chunk_id: str
    chunk_text: str
    similarity: float
    url: str
    title: str
    source: str
    parent_id: str
    chunk_index: int
    passed_threshold: bool


class ContextPassage(BaseModel):
    """One numbered passage as the model saw it.

    ``citation`` is the [n] marker the model was told to cite, so the UI can
    show exactly the list the answer's footnotes refer to. ``similarity`` is
    null for passages pulled in as neighbouring context rather than retrieved
    by score.
    """

    citation: int
    chunk_id: str
    chunk_text: str
    similarity: float | None
    url: str
    title: str
    source: str
    chunk_index: int


class Usage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None


class SearchResponse(BaseModel):
    mode: Literal["search"] = "search"
    query: str
    threshold: float
    top_k: int
    grounded: bool
    best_similarity: float | None = None
    results: list[ChunkResult]
    notice: str | None = None


class AskResponse(BaseModel):
    mode: Literal["rag"] = "rag"
    query: str
    threshold: float
    top_k: int
    grounded: bool
    best_similarity: float | None = None
    answer: str
    refused: bool
    # Which of the two refusal layers fired:
    #   "below_threshold"           -> retrieval gate; the LLM was never called
    #   "model_insufficient_context"-> passages passed the gate but lacked the answer
    refusal_reason: Literal["below_threshold", "model_insufficient_context"] | None = None
    model: str | None = None
    # How many passages were sent to the model: the chunks that passed the
    # threshold plus their adjacent siblings from the same article.
    context_passages: int = 0
    reasoning: str | None = None
    usage: Usage | None = None
    # The numbered passages the answer cites, in the model's numbering.
    context: list[ContextPassage] = []
    # The raw scored hits from the vector database, with their real cosine
    # values — unchanged by context expansion.
    results: list[ChunkResult]


class ConfigResponse(BaseModel):
    collection: str
    chunk_count: int
    embedding_model: str
    embedding_dim: int
    default_threshold: float
    default_top_k: int
    max_top_k: int
    max_query_chars: int
    refusal_message: str
    model_refusal_message: str
    default_model_key: str
    providers: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    detail: str
