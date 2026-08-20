from assistant.tool_call_parser import parse_tool_calls, remove_tool_call_markup


def test_parses_qwen35_tool_call_markup():
    output = """
<think>Need real data.</think>
<tool_call>
<function=search_products>
<parameter=query>
fit kahvaltılık ürünler
</parameter>
<parameter=limit>
5
</parameter>
</function>
</tool_call>
"""
    calls = parse_tool_calls(output)
    assert len(calls) == 1
    assert calls[0].name == "search_products"
    assert calls[0].arguments == {"query": "fit kahvaltılık ürünler", "limit": 5}
    assert remove_tool_call_markup(output) == ""


def test_parses_legacy_custom_tool_call_markup():
    output = (
        '<|tool_call|>{"name":"get_product_details",'
        '"arguments":{"barcode":"3017620422003"}}<|end_tool_call|>'
    )
    calls = parse_tool_calls(output)
    assert len(calls) == 1
    assert calls[0].name == "get_product_details"
    assert calls[0].arguments["barcode"] == "3017620422003"


def test_parses_openai_style_legacy_call():
    output = (
        '<|tool_call|>{"id":"abc","type":"function","function":'
        '{"name":"get_shopping_list","arguments":"{}"}}<|end_tool_call|>'
    )
    calls = parse_tool_calls(output)
    assert calls[0].call_id == "abc"
    assert calls[0].name == "get_shopping_list"
    assert calls[0].arguments == {}


def test_qwen_numeric_barcode_parameter_stays_a_string():
    output = """
<tool_call>
<function=get_product_details>
<parameter=barcode>
08699118072577
</parameter>
</function>
</tool_call>
"""
    calls = parse_tool_calls(output)
    assert calls[0].arguments["barcode"] == "08699118072577"
    assert isinstance(calls[0].arguments["barcode"], str)


def test_parses_recoverable_malformed_qwen_parameter_tags():
    output = """
<tool_call>
<function=search_products>
<parameter=query>
kahvaltılık gevrek
</parameter>
<parameter>max_sugars_100g>
10
</parameter>
<parameter>limit>10</parameter>
</function>
</tool_call>
"""
    calls = parse_tool_calls(output)
    assert calls[0].arguments == {
        "query": "kahvaltılık gevrek",
        "max_sugars_100g": 10,
        "limit": 10,
    }
