from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from models.tool_models import (
    GitHubRepoArguments,
    GitHubSearchArguments,
    PyPIArguments,
    StackOverflowArguments,
)


class PyPICall(BaseModel):
    """
    PyPI paket sorgusu tool çağrısı.
    """

    tool: Literal["search_pypi"]

    arguments: PyPIArguments


class GitHubRepoCall(BaseModel):
    """
    Belirli bir GitHub repository'sini sorgulayan tool çağrısı.
    """

    tool: Literal["search_github_repo"]

    arguments: GitHubRepoArguments


class GitHubSearchCall(BaseModel):
    """
    GitHub üzerinde repository arayan tool çağrısı.
    """

    tool: Literal["search_github_repositories"]

    arguments: GitHubSearchArguments


class StackOverflowCall(BaseModel):
    """
    Stack Overflow üzerinde teknik soru arayan tool çağrısı.
    """

    tool: Literal["search_stackoverflow"]

    arguments: StackOverflowArguments


ToolCall = Annotated[
    Union[
        PyPICall,
        GitHubRepoCall,
        GitHubSearchCall,
        StackOverflowCall,
    ],
    Field(discriminator="tool"),
]


class ToolPlan(BaseModel):
    """
    Planner tarafından oluşturulan tool çalışma planı.
    """

    calls: list[ToolCall] = Field(
        default_factory=list,
        description=(
            "Kullanıcı sorusunu cevaplamak için sırayla "
            "çalıştırılacak tool çağrıları."
        ),
    )