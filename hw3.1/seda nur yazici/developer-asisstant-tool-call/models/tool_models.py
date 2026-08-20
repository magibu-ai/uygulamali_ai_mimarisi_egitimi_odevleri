from pydantic import BaseModel, Field


class PyPIArguments(BaseModel):
    """
    PyPI paket arama aracının argümanları.
    """

    package_name: str = Field(
        ...,
        min_length=1,
        description=(
            "PyPI üzerinde bilgileri alınacak Python paketinin adı. "
            "Örnek: requests, httpx, fastapi"
        ),
    )


class GitHubRepoArguments(BaseModel):
    """
    Belirli bir GitHub repository'sini sorgulayan aracın argümanları.
    """

    owner: str = Field(
        ...,
        min_length=1,
        description=(
            "GitHub repository sahibinin kullanıcı veya organizasyon adı. "
            "Örnek: openai"
        ),
    )

    repo: str = Field(
        ...,
        min_length=1,
        description=(
            "GitHub repository adı. "
            "Örnek: openai-python"
        ),
    )


class GitHubSearchArguments(BaseModel):
    """
    GitHub üzerinde anahtar kelimeyle repository arayan aracın argümanları.
    """

    keyword: str = Field(
        ...,
        min_length=1,
        description=(
            "GitHub repository aramasında kullanılacak sorgu. "
            "Gerektiğinde GitHub Search Query sözdizimi kullanılabilir. "
            "Örnek: LLM agent language:Python"
        ),
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description=(
            "Döndürülecek maksimum repository sayısı. "
            "1 ile 10 arasında olmalıdır."
        ),
    )


class StackOverflowArguments(BaseModel):
    """
    Stack Overflow üzerinde teknik soru veya hata arayan aracın argümanları.
    """

    query: str = Field(
        ...,
        min_length=2,
        description=(
            "Stack Overflow üzerinde aranacak programlama sorusu, "
            "hata mesajı veya teknik konu. "
            "Örnek: Python TypeError list object is not callable"
        ),
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description=(
            "Döndürülecek maksimum Stack Overflow soru sayısı. "
            "1 ile 10 arasında olmalıdır."
        ),
    )