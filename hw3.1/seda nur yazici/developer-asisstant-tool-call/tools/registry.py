from typing import Any, Callable

from tools.github_tool import (
    search_github_repo,
    search_github_repositories,
)
from tools.pypi_tool import search_pypi
from tools.stackoverflow_tool import search_stackoverflow


ToolFunction = Callable[..., dict[str, Any]]


TOOLS: dict[str, ToolFunction] = {
    "search_pypi": search_pypi,
    "search_github_repo": search_github_repo,
    "search_github_repositories": (
        search_github_repositories
    ),
    "search_stackoverflow": search_stackoverflow,
}


def execute_tool(
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Tool adını registry içerisinde bulur ve verilen
    argümanlarla çalıştırır.
    """

    tool = TOOLS.get(name)

    if tool is None:
        available_tools = ", ".join(
            sorted(TOOLS.keys())
        )

        raise ValueError(
            f"'{name}' adlı tool kayıtlı değil. "
            f"Kullanılabilir tool'lar: {available_tools}"
        )

    return tool(**arguments)