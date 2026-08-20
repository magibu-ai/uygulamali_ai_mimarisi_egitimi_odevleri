from odev2_beehive_assistant import app


def test_sensor_table_uses_latest_prior_reading_result_after_recording():
    prior = {
        "hive": {"hive_id": "hive-3"},
        "readings": [{"recorded_at": "2024-01-01T00:00:00Z", "temperature_c": 34.0, "humidity_percent": 60.0, "ph": 5.0, "weight_kg": 30.0}],
    }
    logs = [
        {"name": "get_hive_details", "result": prior},
        {"name": "record_inspection", "result": {"inspection": {"id": 1, "hive_id": "hive-3"}}},
    ]
    frame = app._sensor_frame_from_results({"inspection": {"id": 1}}, logs)
    assert list(frame["temperature_c"]) == [34.0]
    assert list(frame["weight_kg"]) == [30.0]
