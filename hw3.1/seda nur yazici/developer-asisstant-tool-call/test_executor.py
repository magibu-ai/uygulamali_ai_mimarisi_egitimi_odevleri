import json

from executor import run_tool_plan
from llm.planner import create_tool_plan


def main() -> None:
    #user_message = "requests ve httpx paketlerini karşılaştır."
    user_message = "Python ile geliştirilen popüler LLM agent repository'lerini bul."
    
    thinking, plan = create_tool_plan(user_message)

    print("\n--- THINKING ---")
    print(thinking)

    print("\n--- TOOL PLAN ---")
    print(
        json.dumps(
            plan.model_dump(),
            indent=2,
            ensure_ascii=False,
        )
    )

    results = run_tool_plan(plan)

    print("\n--- TOOL RESULTS ---")
    print(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()