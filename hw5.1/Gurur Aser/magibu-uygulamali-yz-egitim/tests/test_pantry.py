from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from les8.pantry import PantryError, PantryStore

TODAY = date(2026, 8, 12)


def write_seed(path: Path, records: list[dict]) -> Path:
    path.write_text(
        json.dumps({"version": 1, "items": records}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def seed_records() -> list[dict]:
    return [
        {
            "id": "milk",
            "name": "Süt",
            "quantity": 1,
            "unit": "litre",
            "category": "süt ürünleri",
            "expires_in_days": 0,
        },
        {
            "id": "tomato",
            "name": "Domates",
            "quantity": 4,
            "unit": "adet",
            "category": "sebze",
            "expires_in_days": 2,
        },
        {
            "id": "yogurt",
            "name": "Yoğurt",
            "quantity": 1,
            "unit": "kase",
            "category": "süt ürünleri",
            "expires_in_days": 3,
        },
        {
            "id": "bread",
            "name": "Ekmek",
            "quantity": 1,
            "unit": "adet",
            "category": "fırın",
            "expires_in_days": -1,
        },
        {
            "id": "rice",
            "name": "Pirinç",
            "quantity": 2,
            "unit": "kg",
            "category": "kuru gıda",
            "expires_in_days": 8,
        },
    ]


def make_store(tmp_path: Path, *, records: list[dict] | None = None) -> PantryStore:
    seed = write_seed(tmp_path / "seed.json", records or seed_records())
    return PantryStore(tmp_path / "state.json", seed_path=seed, today=TODAY)


def test_missing_runtime_materializes_relative_seed_and_uses_iso_dates(tmp_path: Path):
    state = make_store(tmp_path)

    raw = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert all("expires_in_days" not in item for item in raw["items"])
    assert {item["expires_on"] for item in raw["items"]} >= {"2026-08-11", "2026-08-12"}

    result = state.list_items(expiring_within_days=365)
    assert result["today"] == "2026-08-12"
    assert result["count"] == 5
    assert all("days_remaining" in item and "status" in item for item in result["items"])


def test_list_filters_expired_and_sorts_by_date_name_then_id(tmp_path: Path):
    state = make_store(tmp_path)

    result = state.list_items(expiring_within_days=7, include_expired=True)
    assert [item["id"] for item in result["items"]] == ["bread", "milk", "tomato", "yogurt"]
    assert [item["status"] for item in result["items"]] == ["geçmiş", "bugün", "acil", "yakında"]

    without_expired = state.list_items(expiring_within_days=7, include_expired=False)
    assert [item["id"] for item in without_expired["items"]] == ["milk", "tomato", "yogurt"]


def test_status_boundaries_are_deterministic(tmp_path: Path):
    records = [
        {
            "id": f"item-{days}",
            "name": f"Ürün {days}",
            "quantity": 1,
            "unit": "adet",
            "category": "test",
            "expires_in_days": days,
        }
        for days in (-1, 0, 1, 2, 3, 7, 8)
    ]
    state = make_store(tmp_path, records=records)
    items = state.list_items(expiring_within_days=365)["items"]
    statuses = {item["id"]: item["status"] for item in items}
    assert statuses == {
        "item--1": "geçmiş",
        "item-0": "bugün",
        "item-1": "acil",
        "item-2": "acil",
        "item-3": "yakında",
        "item-7": "yakında",
        "item-8": "sonra",
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"expiring_within_days": True}, "expiring_within_days"),
        ({"expiring_within_days": -1}, "expiring_within_days"),
        ({"include_expired": 1}, "include_expired"),
    ],
)
def test_list_rejects_invalid_filters(tmp_path: Path, kwargs: dict, message: str):
    state = make_store(tmp_path)
    with pytest.raises(PantryError, match=message):
        state.list_items(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "quantity": 1, "unit": "adet", "category": "test", "expires_on": "2026-08-12"},
        {"name": "x" * 121, "quantity": 1, "unit": "adet", "category": "test", "expires_on": "2026-08-12"},
        {"name": "x", "quantity": True, "unit": "adet", "category": "test", "expires_on": "2026-08-12"},
        {"name": "x", "quantity": 0, "unit": "adet", "category": "test", "expires_on": "2026-08-12"},
        {"name": "x", "quantity": float("inf"), "unit": "adet", "category": "test", "expires_on": "2026-08-12"},
        {"name": "x", "quantity": 1, "unit": "", "category": "test", "expires_on": "2026-08-12"},
        {"name": "x", "quantity": 1, "unit": "adet", "category": "test", "expires_on": "2026-8-2"},
        {"name": "x", "quantity": 1, "unit": "adet", "category": "test", "expires_on": "2026-02-30"},
    ],
)
def test_add_rejects_invalid_item_values(tmp_path: Path, kwargs: dict):
    state = make_store(tmp_path)
    with pytest.raises(PantryError) as exc_info:
        state.add_item(**kwargs)
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_add_trims_text_and_consume_returns_remaining_then_deletes(tmp_path: Path):
    state = make_store(tmp_path)
    added = state.add_item("  Mercimek  ", 2, "  kg ", "  bakliyat ", "2026-08-20")["item"]
    assert added["name"] == "Mercimek"
    assert added["unit"] == "kg"
    assert added["category"] == "bakliyat"

    partial = state.consume_item(added["id"], 0.5)
    assert partial["deleted"] is False
    assert partial["item"]["quantity"] == 1.5

    deleted = state.consume_item(added["id"], 1.5)
    assert deleted["deleted"] is True
    assert deleted["removed_item"]["id"] == added["id"]
    assert all(item["id"] != added["id"] for item in state.list_items(365)["items"])


def test_consume_and_remove_report_domain_errors(tmp_path: Path):
    state = make_store(tmp_path)
    with pytest.raises(PantryError) as unknown:
        state.consume_item("no-such-item", 1)
    assert unknown.value.code == "UNKNOWN_ITEM"

    with pytest.raises(PantryError) as too_much:
        state.consume_item("milk", 2)
    assert too_much.value.code == "INSUFFICIENT_QUANTITY"

    removed = state.remove_item("milk")
    assert removed["removed_item"]["id"] == "milk"
    with pytest.raises(PantryError) as removed_again:
        state.remove_item("milk")
    assert removed_again.value.code == "UNKNOWN_ITEM"


def test_runtime_json_schema_errors_are_storage_errors(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state_path.write_text('{"version": 1, "items": [{"id": "x", "expires_in_days": 1}]}', encoding="utf-8")
    seed = write_seed(tmp_path / "seed.json", seed_records())
    with pytest.raises(PantryError) as exc_info:
        PantryStore(state_path, seed_path=seed, today=TODAY)
    assert exc_info.value.code == "STORAGE_ERROR"

    state_path.write_text('{"version": 2, "items": []}', encoding="utf-8")
    with pytest.raises(PantryError) as version_error:
        PantryStore(state_path, seed_path=seed, today=TODAY)
    assert version_error.value.code == "STORAGE_ERROR"


def test_missing_seed_error_does_not_expose_local_path(tmp_path: Path):
    missing_seed = tmp_path / "private" / "seed.json"

    with pytest.raises(PantryError) as exc_info:
        PantryStore(tmp_path / "state.json", seed_path=missing_seed, today=TODAY)

    assert exc_info.value.code == "STORAGE_ERROR"
    assert str(tmp_path) not in exc_info.value.message


def test_atomic_write_failure_keeps_previous_file_and_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    state = make_store(tmp_path)
    state_path = tmp_path / "state.json"
    before = state_path.read_bytes()

    def fail_replace(*_args, **_kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("les8.pantry.os.replace", fail_replace)
    with pytest.raises(PantryError) as exc_info:
        state.add_item("Armut", 1, "adet", "meyve", "2026-08-20")
    assert exc_info.value.code == "STORAGE_ERROR"
    assert state_path.read_bytes() == before
    assert all(item["name"] != "Armut" for item in state.list_items(365)["items"])


def test_example_seed_has_relative_dates_and_materializes(tmp_path: Path):
    seed = Path(__file__).parents[1] / "data" / "pantry.example.json"
    raw = json.loads(seed.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["items"]
    assert all("expires_in_days" in item and "expires_on" not in item for item in raw["items"])

    store = PantryStore(tmp_path / "state.json", seed_path=seed, today=TODAY)
    assert store.list_items(365)["count"] == len(raw["items"])
