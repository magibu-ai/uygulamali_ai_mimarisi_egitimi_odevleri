from llm.planner import create_tool_plan


def main() -> None:
    thinking, plan = create_tool_plan(
        "Compare requests and httpx."
    )

    print("\n--- THINKING ---")
    print(thinking)

    print("\n--- TOOL PLAN ---")
    print(plan.model_dump_json(indent=2))


if __name__ == "__main__":
    main()