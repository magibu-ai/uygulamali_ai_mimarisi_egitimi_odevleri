from les8.live_eval import Scenario, assess_scenario


def test_assessment_accepts_required_tool_and_expected_state_change():
    scenario = Scenario(
        name="confirmed_add",
        prompts=("ürün ekle", "onayla"),
        required_tools=frozenset({"add_pantry_item"}),
        expected_pending=False,
        expected_state_change=True,
        reply_terms=("uygulandı",),
    )
    turns = [
        {
            "reply": "Onay bekleniyor.",
            "pending": True,
            "tool_logs": [{"name": "add_pantry_item"}],
        },
        {
            "reply": "İşlem onaylandı ve uygulandı.",
            "pending": False,
            "tool_logs": [{"name": "add_pantry_item"}],
        },
    ]

    passed, reasons = assess_scenario(scenario, turns, state_changed=True)

    assert passed is True
    assert reasons == []


def test_assessment_reports_missing_tool_forbidden_tool_and_state_mutation():
    scenario = Scenario(
        name="cancelled_remove",
        prompts=("ürünü sil", "iptal"),
        required_tools=frozenset({"remove_pantry_item"}),
        forbidden_tools=frozenset({"internet_search"}),
        expected_pending=False,
        expected_state_change=False,
        reply_terms=("iptal",),
    )
    turns = [
        {
            "reply": "Web araması yaptım.",
            "pending": True,
            "tool_logs": [{"name": "internet_search"}],
        },
        {"reply": "Bitti.", "pending": False, "tool_logs": []},
    ]

    passed, reasons = assess_scenario(scenario, turns, state_changed=True)

    assert passed is False
    assert any("eksik araç" in reason for reason in reasons)
    assert any("yasak araç" in reason for reason in reasons)
    assert any("durum dosyası" in reason for reason in reasons)
    assert any("yanıt terimi" in reason for reason in reasons)
