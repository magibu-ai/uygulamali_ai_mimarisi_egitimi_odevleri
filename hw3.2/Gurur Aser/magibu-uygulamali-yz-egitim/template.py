"""Render the local HF chat template without downloading a tokenizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_PATH = Path(__file__).with_name("chat_template.jinja")


def _raise_exception(message: str) -> None:
    raise ValueError(message)


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_PATH.parent)),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        autoescape=False,
    )
    env.globals["raise_exception"] = _raise_exception
    return env


def render_chat(
    messages: Iterable[Mapping[str, Any]],
    *,
    tools: list[Mapping[str, Any]] | None = None,
    add_generation_prompt: bool = False,
) -> str:
    """Render messages using the same template contract as Transformers.

    ``messages`` intentionally accepts dictionaries rather than OpenAI SDK
    objects, making the function useful for tests, the render demo, and a
    tokenizer's ``apply_chat_template`` call.
    """

    normalized = [dict(message) for message in messages]
    # Fail at the boundary with the same message as the template's
    # ``raise_exception`` path, rather than silently dropping a role.
    supported = {"system", "user", "assistant", "tool"}
    for message in normalized:
        role = message.get("role")
        if role not in supported:
            raise ValueError(f"Unsupported message role: {role}")
    template = _environment().get_template(TEMPLATE_PATH.name)
    return template.render(
        messages=normalized,
        tools=tools or [],
        add_generation_prompt=add_generation_prompt,
    )


def render_json(messages: Iterable[Mapping[str, Any]], **kwargs: Any) -> str:
    """Convenience wrapper used by examples and smoke tests."""

    return render_chat(json.loads(json.dumps(list(messages))), **kwargs)


__all__ = ["TEMPLATE_PATH", "render_chat", "render_json"]
