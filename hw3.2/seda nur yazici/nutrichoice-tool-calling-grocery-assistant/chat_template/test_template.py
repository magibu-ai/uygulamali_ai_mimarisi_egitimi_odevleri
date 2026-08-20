from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]


def raise_exception(message: str) -> None:
    raise ValueError(message)


def main() -> None:
    template_text = (ROOT / "chat_template" / "chat_template.jinja").read_text(
        encoding="utf-8"
    )
    example = json.loads(
        (ROOT / "chat_template" / "example_messages.json").read_text(encoding="utf-8")
    )
    tools = json.loads(
        (ROOT / "chat_template" / "tool_definitions.json").read_text(encoding="utf-8")
    )

    env = Environment(undefined=StrictUndefined, autoescape=False)
    env.globals["raise_exception"] = raise_exception
    rendered = env.from_string(template_text).render(
        messages=example["messages"],
        tools=tools,
        bos_token="<s>",
        add_generation_prompt=True,
    )
    print(rendered)


if __name__ == "__main__":
    main()
