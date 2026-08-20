import pytest

from turkish_medical_vector_search.vectorstore.chroma import (
    batched,
    cosine_distance_to_similarity,
)


@pytest.mark.parametrize(
    ("distance", "similarity"),
    [(0.0, 1.0), (0.25, 0.75), (1.0, 0.0), (2.0, -1.0)],
)
def test_cosine_distance_conversion(distance: float, similarity: float) -> None:
    assert cosine_distance_to_similarity(distance) == pytest.approx(similarity)


def test_batched_preserves_order() -> None:
    assert list(batched([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]

