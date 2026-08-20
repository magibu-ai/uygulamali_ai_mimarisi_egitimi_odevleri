from pathlib import Path

from odev2_beehive_assistant.data_loader import DATASET_PATH, load_sensor_data
from odev2_beehive_assistant.database import HiveDatabase, create_session_database


def test_source_dataset_has_exactly_3000_rows_and_expected_metrics():
    rows = load_sensor_data(DATASET_PATH)
    assert len(rows) == 3000
    assert {"temperature_c", "humidity_percent", "ph", "weight_kg"}.issubset(rows[0])


def test_seed_database_has_six_hives_and_3000_readings(tmp_path):
    db = HiveDatabase(tmp_path / "seed.sqlite3")
    db.initialize()
    assert db.count("hives") == 6
    assert db.count("sensor_readings") == 3000
    db.close()


def test_two_session_databases_are_isolated(tmp_path):
    first = create_session_database(tmp_path / "first")
    second = create_session_database(tmp_path / "second")
    first.execute("INSERT INTO inspections (hive_id, queen_seen, varroa_count, notes, inspected_at) VALUES (?, ?, ?, ?, ?)", ("hive-1", 1, 3, "first", "2024-01-01T00:00:00+00:00"))
    assert first.count("inspections") == 1
    assert second.count("inspections") == 0
    first.close()
    second.close()
