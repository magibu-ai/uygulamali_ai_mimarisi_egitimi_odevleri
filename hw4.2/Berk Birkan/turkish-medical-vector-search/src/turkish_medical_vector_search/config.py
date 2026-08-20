"""Typed configuration models for the reproducible retrieval pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown configuration keys."""

    model_config = ConfigDict(extra="forbid")


class ProjectConfig(StrictModel):
    seed: int = 42


class DatasetConfig(StrictModel):
    repo_id: str
    split: str = "train"
    branch_query: str
    sample_size: int = Field(ge=100, le=1000)
    min_text_length: int = Field(default=200, ge=1)


class ChunkingConfig(StrictModel):
    target_tokens: int = Field(gt=0)
    overlap_tokens: int = Field(ge=0)
    min_chunk_tokens: int = Field(gt=0)
    separators: list[str]

    @model_validator(mode="after")
    def validate_token_limits(self) -> "ChunkingConfig":
        if self.overlap_tokens >= self.target_tokens:
            raise ValueError("overlap_tokens must be smaller than target_tokens")
        if self.min_chunk_tokens > self.target_tokens:
            raise ValueError("min_chunk_tokens must not exceed target_tokens")
        return self


class EmbeddingConfig(StrictModel):
    model_id: str
    dimension: int = Field(gt=0)
    normalize: bool = True
    batch_size: int = Field(gt=0)


class VectorStoreConfig(StrictModel):
    provider: str
    collection_name: str
    distance_metric: str
    persist_directory: Path


class RetrievalConfig(StrictModel):
    top_k: int = Field(gt=0)
    threshold: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    abstention_message: str


class BenchmarkConfig(StrictModel):
    calibration_positive: int = Field(ge=0)
    calibration_negative: int = Field(ge=0)
    test_positive: int = Field(ge=0)
    test_negative: int = Field(ge=0)


class OptionalLlmConfig(StrictModel):
    enabled: bool = False
    model_id: str
    load_in_4bit: bool = True
    max_new_tokens: int = Field(gt=0)


class AppConfig(StrictModel):
    project: ProjectConfig
    dataset: DatasetConfig
    chunking: ChunkingConfig
    embedding: EmbeddingConfig
    vector_store: VectorStoreConfig
    retrieval: RetrievalConfig
    benchmark: BenchmarkConfig
    optional_llm: OptionalLlmConfig


def load_config(path: str | Path) -> AppConfig:
    """Load and validate a YAML pipeline configuration."""

    config_path = Path(path)
    with config_path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file)
    return AppConfig.model_validate(payload)
