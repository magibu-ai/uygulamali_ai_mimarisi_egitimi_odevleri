from pathlib import Path

from pydantic import ValidationError

from llm.client import llm
from llm.schemas import ToolPlan


ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "prompts" / "planner_prompt.txt"
PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


def _create_plan_summary(plan: ToolPlan) -> str:
    """
    Tool planından kullanıcıya gösterilebilecek kısa
    bir planlama özeti oluşturur.
    """

    if not plan.calls:
        return (
            "Bu soru için harici bir araç çağrısı planlanmadı."
        )

    tool_names = {
        "search_pypi": "PyPI paket bilgisi sorgulama",
        "search_github_repo": "GitHub repository inceleme",
        "search_github_repositories": "GitHub repository arama",
        "search_stackoverflow": "Stack Overflow araması",
    }

    lines = [
        f"Toplam {len(plan.calls)} araç çağrısı planlandı:"
    ]

    for index, call in enumerate(plan.calls, start=1):
        tool_description = tool_names.get(
            call.tool,
            call.tool,
        )

        arguments = call.arguments.model_dump(
            mode="json"
        )

        lines.append(
            f"{index}. {tool_description} — "
            f"parametreler: {arguments}"
        )

    return "\n".join(lines)


def create_tool_plan(
    user_message: str,
) -> tuple[str, ToolPlan]:
    if not user_message.strip():
        raise ValueError(
            "Kullanıcı mesajı boş olamaz."
        )

    response = llm.generate(
        messages=[
            {
                "role": "system",
                "content": PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        schema=ToolPlan.model_json_schema(),
        think=True,
    )

    content = response.message.content or ""

    try:
        plan = ToolPlan.model_validate_json(content)
    except ValidationError as exc:
        raise RuntimeError(
            "Planner geçerli bir ToolPlan üretemedi.\n\n"
            f"Model çıktısı:\n{content}\n\n"
            f"Doğrulama hatası:\n{exc}"
        ) from exc

    plan_summary = _create_plan_summary(plan)

    return plan_summary, plan