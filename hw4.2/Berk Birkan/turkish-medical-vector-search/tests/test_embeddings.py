import numpy as np
import pytest

from turkish_medical_vector_search.embeddings.local import LocalSentenceEmbedder


def embedder(*, normalize: bool = True) -> LocalSentenceEmbedder:
    instance = LocalSentenceEmbedder.__new__(LocalSentenceEmbedder)
    instance.expected_dimension = 3
    instance.normalize = normalize
    return instance


def test_validate_enforces_l2_normalization() -> None:
    vectors = np.array([[3.0, 4.0, 0.0], [1.0015, 0.0, 0.0]], dtype=np.float32)

    normalized = embedder()._validate(vectors)

    np.testing.assert_allclose(np.linalg.norm(normalized, axis=1), 1.0, atol=1e-6)
    assert normalized.dtype == np.float32


def test_validate_rejects_zero_length_vector() -> None:
    with pytest.raises(ValueError, match="zero-length"):
        embedder()._validate(np.zeros((1, 3), dtype=np.float32))


def test_validate_preserves_vectors_when_normalization_is_disabled() -> None:
    vectors = np.array([[3.0, 4.0, 0.0]], dtype=np.float32)

    result = embedder(normalize=False)._validate(vectors)

    np.testing.assert_array_equal(result, vectors)
