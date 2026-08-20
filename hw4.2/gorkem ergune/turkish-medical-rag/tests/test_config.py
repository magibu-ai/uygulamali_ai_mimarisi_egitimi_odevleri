"""Phase 0 tests: the configuration infrastructure loads and is well-formed."""
from __future__ import annotations

from src.config import DEFAULT_CONFIG_PATH, load_config


def test_config_file_exists():
    assert DEFAULT_CONFIG_PATH.exists(), DEFAULT_CONFIG_PATH


def test_config_loads_as_mapping():
    config = load_config()
    assert isinstance(config, dict)


def test_required_sections_present():
    config = load_config()
    for key in [
        "seed",
        "dataset",
        "chunking",
        "embedding",
        "vectorstore",
        "retrieval",
        "paths",
    ]:
        assert key in config, f"missing config section: {key}"


def test_reproducibility_and_bounds():
    config = load_config()
    # Seed is fixed for reproducibility.
    assert isinstance(config["seed"], int)
    # Document count within assignment bounds (100-1000).
    assert 100 <= config["dataset"]["document_count"] <= 1000
    # top-k is a positive integer.
    assert isinstance(config["retrieval"]["top_k"], int)
    assert config["retrieval"]["top_k"] > 0


def test_calibrated_values_are_locked():
    config = load_config()
    # embedding.model_name / expected_dim locked in Phase 3; threshold in Phase 6.
    assert config["embedding"]["model_name"] == "ytu-ce-cosmos/turkish-e5-large"
    assert config["embedding"]["expected_dim"] == 1024
    threshold = config["retrieval"]["threshold"]
    assert isinstance(threshold, (int, float))
    assert 0.0 < threshold < 1.0
