"""Sentence Transformers adapter used for both documents and queries."""

from __future__ import annotations


class SentenceTransformerEncoder:
    def __init__(self, model_id: str = "magibu/embeddingmagibu-200m", device: str | None = None):
        from sentence_transformers import SentenceTransformer

        self.model_id = model_id
        self.model = SentenceTransformer(model_id, device=device, tokenizer_kwargs={"extra_special_tokens": {}})

    def token_count(self, text: str) -> int:
        return len(self.model.tokenizer.encode(text, add_special_tokens=True))

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        encoder = getattr(self.model, "encode_document", self.model.encode)
        return encoder(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).tolist()

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        encoder = getattr(self.model, "encode_query", self.model.encode)
        return encoder(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).tolist()
