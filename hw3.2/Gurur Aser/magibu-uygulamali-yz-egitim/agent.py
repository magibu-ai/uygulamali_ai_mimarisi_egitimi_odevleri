"""Tool-calling loop shared by the Gradio UI and deterministic tests."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Mapping, Sequence

try:
    from .llm import HFRouterClient
    from .tools import HiveTools, STATES, TOOL_SCHEMAS
except ImportError:  # pragma: no cover - direct execution from les6/.
    from llm import HFRouterClient
    from tools import HiveTools, STATES, TOOL_SCHEMAS

SYSTEM_PROMPT = """Sen Arı Kovanı Sağlık Asistanısın. Türkçe ve ölçülü yanıt ver.
Kovan bilgisi, sensör ölçümü veya saha kontrolü hakkında herhangi bir sonuç
vermeden önce uygun aracı kullan. Araç sonucu hata döndürürse bilgi uydurma;
hata kodunu ve kullanıcıya yapılacak düzeltmeyi açıkla. Durum etiketleri yalnızca
ölçümlerin kaynak dağılımındaki %10-%90 aralığına dayalı istatistiksel özetlerdir;
tıbbi ya da biyolojik tanı değildir. Nihai yanıtta yalnızca araç sonuçlarında açıkça bulunan sayıları, alanları ve durum etiketlerini aynen aktar; araçta
bulunmayan niteliksel seviye, risk veya biyolojik yorum icat etme. Özellikle
varroa sayısını "düşük" ya da "yüksek" diye sınıflandırma."""

# Public Space boundary/cost limits. Keep these constants in one place so the
# UI, tests, and README describe the same budget.
MAX_USER_MESSAGE_CHARS = 2_000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CONTENT_CHARS = 2_000
MAX_TOOL_ROUNDS = 4
TOOL_CALL_LOGGER = logging.getLogger("les6.agent.tool_calls")


def _configure_tool_logger() -> None:
    """Send compact tool events to stderr once, including on module reload."""

    TOOL_CALL_LOGGER.setLevel(logging.INFO)
    TOOL_CALL_LOGGER.propagate = False
    if not any(getattr(handler, "_les6_tool_handler", False) for handler in TOOL_CALL_LOGGER.handlers):
        handler = logging.StreamHandler()
        handler._les6_tool_handler = True
        handler.setFormatter(logging.Formatter("%(message)s"))
        TOOL_CALL_LOGGER.addHandler(handler)


_configure_tool_logger()


def _validated_log_arguments(name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only type/range-validated public-tool arguments for server logs."""

    if name == "list_hives":
        status = arguments.get("status")
        return {"status": status} if status in STATES else {}
    if name == "get_hive_details":
        result: dict[str, Any] = {}
        if isinstance(arguments.get("hive_id"), str):
            result["hive_id"] = arguments["hive_id"]
        limit = arguments.get("reading_limit", 24)
        if isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= 1000:
            result["reading_limit"] = limit
        return result
    if name == "record_inspection":
        result = {}
        if isinstance(arguments.get("hive_id"), str):
            result["hive_id"] = arguments["hive_id"]
        if isinstance(arguments.get("queen_seen"), bool):
            result["queen_seen"] = arguments["queen_seen"]
        count = arguments.get("varroa_count")
        if isinstance(count, int) and not isinstance(count, bool) and 0 <= count <= 1000:
            result["varroa_count"] = count
        notes = arguments.get("notes")
        if isinstance(notes, str) and len(notes) <= 500:
            result["notes"] = notes
        return result
    return {}


def _message_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, Mapping):
        return dict(message)
    result = {"role": getattr(message, "role", "assistant"), "content": getattr(message, "content", "") or ""}
    calls = getattr(message, "tool_calls", None)
    if calls:
        result["tool_calls"] = calls
    return result


def _tool_call_parts(call: Any, fallback_index: int) -> tuple[str, str, Any]:
    if isinstance(call, Mapping):
        function = call.get("function", {})
        return (
            str(call.get("id") or f"call-{fallback_index}"),
            str(function.get("name") or call.get("name") or ""),
            function.get("arguments", call.get("arguments", {})),
        )
    function = getattr(call, "function", None)
    return (
        str(getattr(call, "id", None) or f"call-{fallback_index}"),
        str(getattr(function, "name", "") or ""),
        getattr(function, "arguments", "{}"),
    )


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _needs_tool(message: str) -> bool:
    keywords = ("kovan", "kovanlar", "arı", "varroa", "kraliçe", "sensör", "ölçüm", "dikkat")
    lowered = message.casefold()
    return any(keyword in lowered for keyword in keywords)


class BeehiveAgent:
    def __init__(self, database: Any, *, client: Any | None = None, max_rounds: int = MAX_TOOL_ROUNDS):
        self.tools = HiveTools(database)
        self.client = client or HFRouterClient()
        try:
            requested_rounds = int(max_rounds)
        except (TypeError, ValueError):
            requested_rounds = MAX_TOOL_ROUNDS
        self.max_rounds = max(1, min(requested_rounds, MAX_TOOL_ROUNDS))

    def _complete(self, messages: Sequence[Mapping[str, Any]], tool_choice: str | None) -> dict[str, Any]:
        try:
            return _message_dict(self.client.complete(messages, TOOL_SCHEMAS, tool_choice=tool_choice))
        except TypeError as exc:
            # Tiny fake clients often omit ``tool_choice``; preserving this
            # adapter keeps tests deterministic without changing the contract.
            if "tool_choice" not in str(exc):
                raise
            return _message_dict(self.client.complete(messages, TOOL_SCHEMAS))

    def respond(self, user_message: str, history: Sequence[Any] | None = None) -> dict[str, Any]:
        if not isinstance(user_message, str) or not user_message.strip():
            return {"reply": "Lütfen bir soru yazın.", "messages": [], "tool_logs": [], "last_result": None}
        if len(user_message) > MAX_USER_MESSAGE_CHARS:
            return {
                "reply": f"Mesaj en fazla {MAX_USER_MESSAGE_CHARS} karakter olabilir.",
                "messages": [],
                "tool_logs": [],
                "last_result": None,
            }
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(self._history_messages(history))
        messages.append({"role": "user", "content": user_message})
        logs: list[dict[str, Any]] = []
        first_request = True
        last_result: dict[str, Any] | None = None

        for _round in range(self.max_rounds):
            tool_choice = "required" if first_request and _needs_tool(user_message) else "auto"
            assistant = self._complete(messages, tool_choice)
            first_request = False
            calls = assistant.get("tool_calls") or []
            if not calls:
                # A provider that ignores required tool choice is handled by a
                # local list call before accepting its prose as final.
                if _round == 0 and _needs_tool(user_message):
                    calls = [{"id": "forced-list-hives", "type": "function", "function": {"name": "list_hives", "arguments": "{}"}}]
                else:
                    messages.append(assistant)
                    return {"reply": assistant.get("content", "") or "", "messages": messages, "tool_logs": logs, "last_result": last_result}
            assistant["tool_calls"] = calls
            messages.append(assistant)
            for index, call in enumerate(calls, start=1):
                call_id, name, raw_args = _tool_call_parts(call, index)
                args = _parse_arguments(raw_args)
                started = time.perf_counter()
                if name not in self.tools.registry():
                    result = {"error": {"code": "UNKNOWN_TOOL", "message": f"Unknown tool: {name}"}}
                else:
                    try:
                        result = self.tools.registry()[name](**args)
                    except TypeError as exc:
                        result = {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
                    except Exception:  # SQLite/provider boundaries must not crash the model loop.
                        result = {"error": {"code": "DATABASE_ERROR", "message": "Tool işlemi tamamlanamadı."}}
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                last_result = result
                result_json = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
                TOOL_CALL_LOGGER.info(
                    json.dumps(
                        {
                            "event": "tool_call",
                            "tool_name": name,
                            "arguments": _validated_log_arguments(name, args),
                            "result_json": result_json,
                            "duration_ms": elapsed_ms,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                logs.append(
                    {
                        "id": call_id,
                        "name": name,
                        "arguments": args,
                        "result": result,
                        "raw_result": result_json,
                        "duration_ms": elapsed_ms,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        return {
            "reply": "Araç sonuçlarını tamamlayamadım; lütfen isteği daha kısa bir soruyla tekrarlayın.",
            "messages": messages,
            "tool_logs": logs,
            "last_result": last_result,
        }

    @staticmethod
    def _history_messages(history: Sequence[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for entry in history:
            # Only client-visible conversational roles are accepted. In
            # particular, never replay client-supplied system/tool metadata or
            # assistant tool_calls into a new model request.
            if isinstance(entry, Mapping) and entry.get("role") in {"user", "assistant"}:
                content = BeehiveAgent._history_content(entry.get("content"))
                if content:
                    result.append({"role": entry["role"], "content": content[:MAX_HISTORY_CONTENT_CHARS]})
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                if entry[0]:
                    result.append({"role": "user", "content": str(entry[0])[:MAX_HISTORY_CONTENT_CHARS]})
                if entry[1]:
                    result.append({"role": "assistant", "content": str(entry[1])[:MAX_HISTORY_CONTENT_CHARS]})
        return result[-MAX_HISTORY_MESSAGES:]

    @staticmethod
    def _history_content(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, Mapping):
            text = value.get("text")
            return str(text) if text is not None else ""
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            parts = []
            for item in value:
                if isinstance(item, Mapping) and item.get("type") == "text" and item.get("text") is not None:
                    parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)
        return ""


def run_assistant(user_message: str, database: Any, *, client: Any | None = None, history: Sequence[Any] | None = None) -> dict[str, Any]:
    return BeehiveAgent(database, client=client).respond(user_message, history)


__all__ = [
    "BeehiveAgent",
    "MAX_HISTORY_CONTENT_CHARS",
    "MAX_HISTORY_MESSAGES",
    "MAX_TOOL_ROUNDS",
    "MAX_USER_MESSAGE_CHARS",
    "SYSTEM_PROMPT",
    "run_assistant",
]
