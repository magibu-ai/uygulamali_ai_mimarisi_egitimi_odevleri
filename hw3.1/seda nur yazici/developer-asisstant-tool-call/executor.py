from models.trace_models import ToolExecutionResult
from tools.registry import execute_tool
from utils.logger import (
    log_error,
    log_success,
    log_tool_start,
)


def run_tool_plan(plan) -> list[ToolExecutionResult]:
    """
    Planner tarafından oluşturulan ToolPlan içindeki
    tüm tool çağrılarını sırayla çalıştırır.

    Args:
        plan:
            Planner tarafından üretilen ToolPlan nesnesi.

    Returns:
        Her tool çağrısı için ToolExecutionResult listesi.
    """

    execution_results: list[ToolExecutionResult] = []

    for step, call in enumerate(plan.calls, start=1):
        tool_name = call.tool

        arguments = call.arguments.model_dump(
            exclude_none=True
        )

        log_tool_start(
            tool_name=tool_name,
            arguments=arguments,
        )

        try:
            result = execute_tool(
                name=tool_name,
                arguments=arguments,
            )

            tool_success = bool(
                result.get("success", True)
            )

            if tool_success:
                log_success(
                    f"{tool_name} başarıyla çalıştı."
                )
            else:
                log_error(
                    result.get(
                        "error",
                        f"{tool_name} başarısız oldu.",
                    )
                )

            execution_results.append(
                ToolExecutionResult(
                    step=step,
                    tool=tool_name,
                    arguments=arguments,
                    success=tool_success,
                    result=result,
                    error=(
                        None
                        if tool_success
                        else result.get("error")
                    ),
                )
            )

        except Exception as exc:
            error_message = str(exc)

            log_error(
                f"{tool_name} çalıştırılırken hata oluştu: "
                f"{error_message}"
            )

            execution_results.append(
                ToolExecutionResult(
                    step=step,
                    tool=tool_name,
                    arguments=arguments,
                    success=False,
                    result=None,
                    error=error_message,
                )
            )

    return execution_results