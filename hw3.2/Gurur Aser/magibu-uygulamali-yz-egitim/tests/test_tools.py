from odev2_beehive_assistant.database import create_session_database
from odev2_beehive_assistant.tools import HiveTools, TOOL_SCHEMAS


def test_tools_report_status_and_outliers(tmp_path):
    db = create_session_database(tmp_path / "session")
    tools = HiveTools(db)
    result = tools.list_hives()
    assert "hives" in result and len(result["hives"]) == 6
    assert {item["status"] for item in result["hives"]}.issubset({"normal", "izle", "dikkat"})
    assert all("outlier_metrics" in item and "latest_reading" in item for item in result["hives"])
    db.close()


def test_tool_validation_returns_structured_errors(tmp_path):
    db = create_session_database(tmp_path / "session")
    tools = HiveTools(db)
    assert tools.get_hive_details("does-not-exist")["error"]["code"] == "UNKNOWN_HIVE"
    assert tools.record_inspection("hive-1", True, -1, "")["error"]["code"] == "VALIDATION_ERROR"
    assert tools.record_inspection("hive-1", True, 1, "x" * 501)["error"]["code"] == "VALIDATION_ERROR"
    db.close()


def test_tool_schemas_match_public_signatures():
    names = {item["function"]["name"] for item in TOOL_SCHEMAS}
    assert names == {"list_hives", "get_hive_details", "record_inspection"}
    record = next(item for item in TOOL_SCHEMAS if item["function"]["name"] == "record_inspection")
    assert set(record["function"]["parameters"]["required"]) == {"hive_id", "queen_seen", "varroa_count", "notes"}
