from typing import Any

from pydantic import BaseModel, Field


class ToolExecutionResult(BaseModel):
    """
    Tek bir tool çağrısının çalışma sonucunu temsil eder.
    """

    step: int = Field(
        ...,
        ge=1,
        description="Tool çağrısının çalışma sırası.",
    )

    tool: str = Field(
        ...,
        min_length=1,
        description="Çalıştırılan tool adı.",
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool'a gönderilen argümanlar.",
    )

    success: bool = Field(
        ...,
        description="Tool çağrısının başarılı olup olmadığı.",
    )

    result: dict[str, Any] | None = Field(
        default=None,
        description="Tool tarafından döndürülen sonuç.",
    )

    error: str | None = Field(
        default=None,
        description="Tool çalıştırılırken oluşan hata.",
    )