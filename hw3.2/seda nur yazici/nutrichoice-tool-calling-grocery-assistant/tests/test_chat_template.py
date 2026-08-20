from pathlib import Path

from jinja2 import Environment, StrictUndefined

from tools.definitions import TOOL_DEFINITIONS


def raise_exception(message: str) -> None:
    raise ValueError(message)


def test_template_renders_qwen_roles_tools_and_generation_prompt():
    root = Path(__file__).resolve().parents[1]
    template_text = (root / "chat_template" / "chat_template.jinja").read_text(
        encoding="utf-8"
    )
    env = Environment(undefined=StrictUndefined, autoescape=False)
    env.globals["raise_exception"] = raise_exception
    template = env.from_string(template_text)
    rendered = template.render(
        add_generation_prompt=True,
        enable_thinking=False,
        tools=TOOL_DEFINITIONS,
        messages=[
            {"role": "system", "content": "System rule"},
            {"role": "user", "content": "Find cereal"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_0",
                        "type": "function",
                        "function": {
                            "name": "search_products",
                            "arguments": {"query": "cereal"},
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_0",
                "name": "search_products",
                "content": '{"success":true}',
            },
        ],
    )
    assert "<tools>" in rendered
    assert "<|im_start|>user" in rendered
    assert "<tool_call>" in rendered
    assert "<function=search_products>" in rendered
    assert "<tool_response>" in rendered
    assert rendered.rstrip().endswith("</think>")
