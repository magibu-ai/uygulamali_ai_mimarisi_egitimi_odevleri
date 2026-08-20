from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


# Legacy format kept so the rule-based development backend and older tests still work.
LEGACY_TOOL_CALL_PATTERN = re.compile(
    r"<\|tool_call\|>\s*(\{.*?\})\s*<\|end_tool_call\|>", re.DOTALL
)

# Qwen3.5 native function-call format.
QWEN_TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL | re.IGNORECASE
)
QWEN_FUNCTION_PATTERN = re.compile(
    r"<function=([A-Za-z_][\w.\-]*)>\s*(.*?)\s*</function>",
    re.DOTALL | re.IGNORECASE,
)
# Qwen normally emits <parameter=name>value</parameter>. Very small models can
# occasionally emit the recoverable variant <parameter>name>value</parameter>.
# Accept both forms, while still restricting parameter names to safe identifiers.
QWEN_PARAMETER_PATTERN = re.compile(
    r"<parameter(?:=([A-Za-z_][\w.\-]*)|>([A-Za-z_][\w.\-]*))>"
    r"\s*(.*?)\s*</parameter>",
    re.DOTALL | re.IGNORECASE,
)
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class ParsedToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str


def _normalize_tool_call(payload: dict[str, Any], index: int) -> ParsedToolCall:
    if "function" in payload and isinstance(payload["function"], dict):
        function = payload["function"]
        name = function.get("name")
        arguments = function.get("arguments", {})
        call_id = payload.get("id", f"call_{index}")
    else:
        name = payload.get("name")
        arguments = payload.get("arguments", {})
        call_id = payload.get("id", f"call_{index}")

    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Tool call is missing a valid name.")
    if not isinstance(arguments, dict):
        raise ValueError("Tool call arguments must be a JSON object.")

    return ParsedToolCall(name=name.strip(), arguments=arguments, call_id=str(call_id))


STRING_IDENTIFIER_PARAMETERS = {"barcode"}


def _parse_parameter_value(parameter_name: str, raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        return ""

    # Identifiers such as barcodes are strings even when every character is a digit.
    # Parsing an unquoted barcode with json.loads would incorrectly turn it into int.
    if parameter_name.casefold() in STRING_IDENTIFIER_PARAMETERS:
        if value.startswith('"') and value.endswith('"'):
            try:
                parsed = json.loads(value)
                return str(parsed)
            except json.JSONDecodeError:
                pass
        return value

    # Qwen emits plain text for strings and JSON for structured/scalar values.
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_qwen_calls(text: str, starting_index: int = 0) -> list[ParsedToolCall]:
    calls: list[ParsedToolCall] = []
    for block in QWEN_TOOL_CALL_PATTERN.findall(text):
        function_matches = QWEN_FUNCTION_PATTERN.findall(block)
        if not function_matches:
            raise ValueError("Qwen tool-call block is missing a function element.")

        for function_name, function_body in function_matches:
            arguments: dict[str, Any] = {}
            for normal_name, malformed_name, raw_value in QWEN_PARAMETER_PATTERN.findall(
                function_body
            ):
                parameter_name = normal_name or malformed_name
                arguments[parameter_name] = _parse_parameter_value(
                    parameter_name, raw_value
                )

            calls.append(
                ParsedToolCall(
                    name=function_name.strip(),
                    arguments=arguments,
                    call_id=f"call_{starting_index + len(calls)}",
                )
            )
    return calls


def parse_tool_calls(text: str) -> list[ParsedToolCall]:
    qwen_calls = _parse_qwen_calls(text)
    if qwen_calls:
        return qwen_calls

    matches = LEGACY_TOOL_CALL_PATTERN.findall(text)
    payloads: list[dict[str, Any]] = []

    if matches:
        for raw in matches:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("Tool-call payload must be a JSON object.")
            payloads.append(payload)
    else:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            payload = json.loads(stripped)
            if isinstance(payload, dict) and ("name" in payload or "function" in payload):
                payloads.append(payload)

    return [_normalize_tool_call(payload, index) for index, payload in enumerate(payloads)]


def remove_tool_call_markup(text: str) -> str:
    cleaned = QWEN_TOOL_CALL_PATTERN.sub("", text)
    cleaned = LEGACY_TOOL_CALL_PATTERN.sub("", cleaned)

    # Do not feed hidden reasoning back into later turns or show it to the user.
    if "</think>" in cleaned:
        cleaned = cleaned.rsplit("</think>", 1)[-1]
    cleaned = THINK_BLOCK_PATTERN.sub("", cleaned)

    for token in ("<|im_start|>", "<|im_end|>", "<|endoftext|>"):
        cleaned = cleaned.replace(token, "")
    return cleaned.strip()
