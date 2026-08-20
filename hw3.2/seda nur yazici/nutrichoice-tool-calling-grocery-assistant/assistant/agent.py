from __future__ import annotations

import hashlib
import os
import threading
from typing import Any

from assistant.conversation_state import SessionStateStore
from assistant.entity_resolver import EntityResolver
from assistant.intent_planner import IntentPlanner
from assistant.model_client import ModelClient, build_model_client
from assistant.response_formatter import ResponseFormatter
from services.open_food_facts import OpenFoodFactsClient
from tools.tool_router import ToolRouter


class NutriChoiceAgent:
    """Orchestrates planning, structured state, reference resolution and tool execution."""

    def __init__(
        self,
        model: ModelClient,
        router: ToolRouter | Any,
        *,
        state_store: SessionStateStore | None = None,
        planner: IntentPlanner | None = None,
        resolver: EntityResolver | None = None,
        formatter: ResponseFormatter | None = None,
    ):
        self.model = model
        self.base_router = router
        self.state_store = state_store or SessionStateStore()
        self.planner = planner or IntentPlanner(model)
        self.resolver = resolver or EntityResolver()
        self.formatter = formatter or ResponseFormatter()
        self._session_routers: dict[str, ToolRouter | Any] = {"default": router}
        self._router_lock = threading.RLock()

    @classmethod
    def from_environment(cls) -> "NutriChoiceAgent":
        client = OpenFoodFactsClient.from_environment()
        router = ToolRouter(
            off_client=client,
            user_id=os.getenv("DEFAULT_USER_ID", "demo-user"),
        )
        return cls(model=build_model_client(), router=router)

    def chat(
        self,
        user_message: str,
        history: list[dict[str, Any]] | None = None,
        *,
        session_id: str = "default",
    ) -> str:
        del history
        state = self.state_store.get(session_id)
        plans = self.planner.create_plans(user_message, state)
        router = self._router_for(session_id)
        executions: list[tuple[Any, list[tuple[Any, dict[str, Any]]]]] = []

        for plan in plans:
            resolution = self.resolver.resolve(plan, state)
            if resolution.clarification:
                # Do not execute a partial batch when one step is ambiguous. Asking is
                # safer than adding/removing the wrong product.
                return resolution.clarification

            print(f"TOOL_ROUTING source=stateful_action_plan action={plan.action.value}", flush=True)
            calls_and_results = [
                (call, router.execute(call.name, call.arguments))
                for call in resolution.calls
            ]
            state.update(plan, calls_and_results)
            executions.append((plan, calls_and_results))

        return self.formatter.format_batch(executions)

    def _router_for(self, session_id: str) -> ToolRouter | Any:
        key = session_id or "default"
        if key == "default" or not isinstance(self.base_router, ToolRouter):
            return self.base_router

        with self._router_lock:
            existing = self._session_routers.get(key)
            if existing is not None:
                return existing
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            user_id = f"{self.base_router.user_id}:{digest}"
            router = ToolRouter(
                off_client=self.base_router.off_client,
                user_id=user_id,
            )
            self._session_routers[key] = router
            return router
