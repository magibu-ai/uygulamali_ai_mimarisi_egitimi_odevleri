import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_materialized_benchmark_distribution_and_evidence() -> None:
    root = Path(__file__).parents[1] / "data" / "benchmark"
    calibration = read_jsonl(root / "calibration.jsonl")
    test = read_jsonl(root / "test.jsonl")

    assert len(calibration) == 20
    assert sum(row["is_answerable"] for row in calibration) == 10
    assert len(test) == 30
    assert sum(row["is_answerable"] for row in test) == 20
    assert all(row["expected_chunk_id"] for row in calibration + test if row["is_answerable"])
    assert all(row["expected_chunk_id"] is None for row in calibration + test if not row["is_answerable"])
    assert len({row["question_id"] for row in calibration + test}) == 50

