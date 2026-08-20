from pathlib import Path

import pytest
from pydantic import ValidationError

from turkish_medical_vector_search.config import ChunkingConfig, load_config


def test_default_config_loads() -> None:
    config_path = Path(__file__).parents[1] / "configs" / "default.yaml"
    config = load_config(config_path)

    assert config.dataset.sample_size == 500
    assert config.dataset.branch_query == "Dermatoloji"
    assert config.chunking.target_tokens == 512
    assert config.chunking.overlap_tokens == 64
    assert config.embedding.model_id == "magibu/embeddingmagibu-200m"
    assert config.embedding.dimension == 768
    assert config.retrieval.threshold == 0.4240
    assert config.optional_llm.enabled is False


def test_overlap_must_be_smaller_than_target() -> None:
    with pytest.raises(ValidationError, match="overlap_tokens"):
        ChunkingConfig(
            target_tokens=128,
            overlap_tokens=128,
            min_chunk_tokens=32,
            separators=["\n\n"],
        )
