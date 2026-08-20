import json

from tools.stackoverflow_tool import (
    search_stackoverflow,
)


def main() -> None:
    result = search_stackoverflow(
        query=(
            "Python TypeError object is not subscriptable"
        ),
        limit=5,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()