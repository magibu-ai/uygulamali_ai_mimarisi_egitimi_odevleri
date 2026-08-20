import json

from executor import run_tool_plan
from llm.planner import create_tool_plan
from llm.responder import generate_response


def main() -> None:
    user_message = (
        "requests ve httpx paketlerini karşılaştır."
    )

    thinking, plan = create_tool_plan(user_message)

    print("\n--- THINKING ---")
    print(thinking)

    print("\n--- TOOL PLAN ---")
    print(plan.model_dump_json(indent=2))

    tool_results = run_tool_plan(plan)

    print("\n--- TOOL RESULTS ---")
    print(
        json.dumps(
            [
                result.model_dump(mode="json")
                for result in tool_results
            ],
            indent=2,
            ensure_ascii=False,
        )
    )

    answer = generate_response(
        user_message=user_message,
        tool_results=tool_results,
    )

    print("\n--- FINAL ANSWER ---")
    print(answer)


if __name__ == "__main__":
    main()