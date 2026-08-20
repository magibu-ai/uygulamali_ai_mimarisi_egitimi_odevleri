import json

from agent import run_agent


def main() -> None:
    user_message = (
        "Python'da TypeError: 'list' object is not callable "
        "hatası alıyorum. Benzer Stack Overflow sorularını "
        "bul ve kısaca açıkla."
    )

    (
        thinking,
        plan,
        tool_results,
        final_answer,
    ) = run_agent(user_message)

    print("\n--- THINKING ---")
    print(thinking)

    print("\n--- TOOL PLAN ---")
    print(
        json.dumps(
            plan,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\n--- TOOL RESULTS ---")
    print(
        json.dumps(
            tool_results,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\n--- FINAL ANSWER ---")
    print(final_answer)


if __name__ == "__main__":
    main()