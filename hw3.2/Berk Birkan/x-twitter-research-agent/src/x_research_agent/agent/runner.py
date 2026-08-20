from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from x_research_agent.config import Settings
from x_research_agent.domain.schemas import ResearchConstraints, ToolCallRecord
from x_research_agent.providers.openrouter import OpenRouterClient, OpenRouterError
from x_research_agent.providers.xquik import XquikClient
from x_research_agent.tools.definitions import TOOL_DEFINITIONS
from x_research_agent.tools.dispatcher import ToolDispatcher, ToolExecutionError
from x_research_agent.tools.runtime import AgentRuntime

from .prompts import SYSTEM_PROMPT


class AgentError(RuntimeError):
    pass


class AgentRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def run(
        self,
        *,
        user_message: str,
        session_id: str,
        model_id: str,
        openrouter_key: str,
        xquik_key: str,
        constraints: ResearchConstraints,
        conversation: list[dict[str, Any]] | None = None,
        runtime: AgentRuntime | None = None,
        progress: Callable[[ToolCallRecord], None] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], AgentRuntime, dict[str, Any]]:
        if not user_message.strip():
            raise AgentError("Research question cannot be empty")
        if runtime is None:
            runtime = AgentRuntime(
                session_id=session_id,
                user_question=user_message,
                selected_model=model_id,
                constraints=constraints,
            )
        elif runtime.finalized:
            runtime.search_cache.clear()
            runtime.searched_keys.clear()
            runtime.saved_search_ids.clear()
            runtime.unique_post_ids.clear()
            runtime.search_calls = 0
            runtime.finalize_attempts = 0
            runtime.cancelled.clear()
        runtime.user_question = user_message
        runtime.selected_model = model_id
        runtime.constraints = constraints
        runtime.finalized = False
        runtime.latest_report = None
        runtime.latest_version = None
        messages = list(conversation or [])
        if not messages:
            messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append(
            {
                "role": "user",
                "content": self._user_prompt(user_message, constraints, runtime),
            }
        )
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        async with (
            OpenRouterClient(
                openrouter_key,
                base_url=self.settings.openrouter_base_url,
                app_url=self.settings.openrouter_app_url,
                app_name=self.settings.openrouter_app_name,
                timeout=max(self.settings.request_timeout_seconds, 60),
            ) as openrouter,
            XquikClient(
                xquik_key,
                base_url=self.settings.xquik_base_url,
                timeout=self.settings.request_timeout_seconds,
            ) as xquik,
        ):
            dispatcher = ToolDispatcher(
                settings=self.settings, runtime=runtime, xquik=xquik, progress=progress
            )
            for _step in range(self.settings.max_agent_steps):
                if runtime.cancelled.is_set():
                    raise AgentError("Research was cancelled")
                response = await openrouter.chat_completion(
                    model=model_id,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                )
                self._accumulate_usage(usage_total, response.get("usage") or {})
                try:
                    assistant_message = response["choices"][0]["message"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise OpenRouterError("OpenRouter returned an invalid chat response") from exc
                messages.append(self._clean_assistant_message(assistant_message))
                tool_calls = assistant_message.get("tool_calls") or []
                if not tool_calls:
                    messages.append(
                        {
                            "role": "user",
                            "content": "Continue using tools. A successful turn must call "
                            "finalize_research; do not answer only with text.",
                        }
                    )
                    continue
                for tool_call in tool_calls:
                    function = tool_call.get("function") or {}
                    name = function.get("name", "")
                    try:
                        result = await dispatcher.execute(name, function.get("arguments", "{}"))
                    except ToolExecutionError as exc:
                        result = {"error": str(exc), "tool": name}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id"),
                            "name": name,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                if runtime.finalized and runtime.latest_report:
                    return runtime.latest_report, messages, runtime, usage_total
        raise AgentError("Agent reached its step limit without saving a valid report")

    @staticmethod
    def _clean_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
        clean = {"role": "assistant", "content": message.get("content")}
        if message.get("tool_calls"):
            clean["tool_calls"] = message["tool_calls"]
        return clean

    @staticmethod
    def _user_prompt(
        user_message: str, constraints: ResearchConstraints, runtime: AgentRuntime
    ) -> str:
        return (
            f"Research request:\n{user_message}\n\n"
            f"Objective constraints (enforced by application): "
            f"{constraints.model_dump(mode='json')}\n"
            f"Unique post budget remaining: {runtime.remaining_budget}."
        )

    @staticmethod
    def _accumulate_usage(total: dict[str, Any], usage: dict[str, Any]) -> None:
        total["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
        total["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)
        total["cost"] += float(usage.get("cost", 0) or 0)
