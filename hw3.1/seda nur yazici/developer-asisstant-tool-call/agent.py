from typing import Any

from executor import run_tool_plan
from llm.planner import create_tool_plan
from llm.responder import generate_response
from models.trace_models import ToolExecutionResult


def run_agent(
    user_message: str,
) -> tuple[
    str,
    dict[str, Any],
    list[dict[str, Any]],
    str,
]:
    """
    AI Developer Assistant pipeline'ını çalıştırır.

    Akış:
        Kullanıcı mesajı
            -> Planner
            -> ToolPlan
            -> Executor
            -> Tool sonuçları
            -> Responder
            -> Nihai cevap

    Args:
        user_message:
            Kullanıcının geliştirici sorusu.

    Returns:
        thinking:
            Planner modelinin analiz metni.

        plan_data:
            Tool planının sözlük biçimi.

        execution_data:
            Tool çalışma sonuçlarının sözlük listesi.

        final_answer:
            Kullanıcıya gösterilecek nihai cevap.
    """

    cleaned_message = user_message.strip()

    if not cleaned_message:
        raise ValueError(
            "Lütfen bir soru girin."
        )

    # 1. Planner
    thinking, plan = create_tool_plan(
        cleaned_message
    )

    # 2. Executor
    tool_results: list[ToolExecutionResult] = (
        run_tool_plan(plan)
    )

    # 3. Responder
    final_answer = generate_response(
        user_message=cleaned_message,
        tool_results=tool_results,
    )

    # Gradio JSON bileşenlerinin doğrudan
    # gösterebilmesi için Pydantic modellerini
    # standart Python sözlüklerine dönüştürüyoruz.
    plan_data = plan.model_dump(mode="json")

    execution_data = [
        result.model_dump(mode="json")
        for result in tool_results
    ]

    return (
        thinking.strip(),
        plan_data,
        execution_data,
        final_answer.strip(),
    )