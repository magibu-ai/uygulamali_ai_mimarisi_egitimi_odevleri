import json
from pathlib import Path

import pytest

from odev1_custom_chat_template.template import render_chat, TEMPLATE_PATH


def test_template_path_exists_and_renders_every_supported_role():
    assert TEMPLATE_PATH.exists()
    rendered = render_chat(
        [
            {"role": "system", "content": "Kurallar"},
            {"role": "user", "content": "Merhaba"},
            {"role": "assistant", "content": "Merhaba!"},
            {"role": "tool", "tool_call_id": "call-1", "name": "get_weather", "content": '{"city": "İstanbul", "temperature_c": 24}'},
        ]
    )
    assert "<|im_start|>system" in rendered
    assert "<|im_start|>user" in rendered
    assert "<|im_start|>assistant" in rendered
    assert "<|im_start|>tool" in rendered
    assert "<|tool_result|>" in rendered
    assert "call-1" in rendered


def test_template_serializes_tools_after_system_and_multiple_calls():
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}]
    rendered = render_chat(
        [
            {"role": "system", "content": "Kurallar"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call-1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city":"İstanbul"}'}},
                    {"id": "call-2", "type": "function", "function": {"name": "get_weather", "arguments": '{"city":"Ankara"}'}},
                ],
            },
        ],
        tools=tools,
    )
    assert json.dumps(tools, ensure_ascii=False)[:20] in rendered or '"get_weather"' in rendered
    assert "call-1" in rendered and "call-2" in rendered
    assert rendered.count("<|tool_call|>") == 2


def test_template_adds_generation_prompt_and_rejects_unknown_role():
    rendered = render_chat([{"role": "user", "content": "İstanbul hava durumunu göster"}], add_generation_prompt=True)
    assert rendered.endswith("<|im_start|>assistant\n")
    with pytest.raises(Exception):
        render_chat([{"role": "developer", "content": "yasak"}])
