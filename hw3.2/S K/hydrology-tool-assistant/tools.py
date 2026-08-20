import database


def execute_tool(func_name, kwargs):
    """LLM'in JSON tool çağrısını izin verilen Python fonksiyonuna yönlendirir."""
    allowed_tools = {
        "list_stations": database.list_stations,
        "get_latest_measurement": database.get_latest_measurement,
        "create_flow_alert": database.create_flow_alert,
        "create_flow_alerts": database.create_flow_alerts,
        "list_flow_alerts": database.list_flow_alerts,
    }

    function = allowed_tools.get(func_name)
    if function is None:
        return {"success": False, "message": f"Bilinmeyen araç çağrısı: {func_name}"}

    try:
        return function(**kwargs)
    except TypeError as exc:
        return {
            "success": False,
            "message": f"Araç parametreleri geçersiz: {exc}",
        }
