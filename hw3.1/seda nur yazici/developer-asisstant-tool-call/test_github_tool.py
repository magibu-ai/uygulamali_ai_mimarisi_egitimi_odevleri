import json

from tools.github_tool import (
    search_github_repo,
    search_github_repositories,
)


def main() -> None:
    print("\n--- BELİRLİ REPOSITORY TESTİ ---")

    repository_result = search_github_repo(
        owner="openai",
        repo="openai-python",
    )

    print(
        json.dumps(
            repository_result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\n--- REPOSITORY ARAMA TESTİ ---")

    search_result = search_github_repositories(
        keyword="python llm agent",
        limit=3,
    )

    print(
        json.dumps(
            search_result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()