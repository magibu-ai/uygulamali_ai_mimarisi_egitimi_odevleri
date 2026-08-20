"""Strict runtime validation for arguments authored by a model."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from uuid import UUID

# None can be a meaningful JSON value. A private sentinel distinguishes an omitted
# argument from an explicitly supplied null.
_MISSING = object()


class ToolArgumentError(ValueError):
    """Raised when model-provided tool arguments do not match the declaration."""


class Arguments:
    """Strict parser that rejects missing, malformed, and undeclared arguments."""

    def __init__(self, arguments: Mapping[str, object]) -> None:
        self._values = dict(arguments)

    def required_string(self, name: str) -> str:
        value = self._pop_required(name)
        if not isinstance(value, str) or not value.strip():
            raise ToolArgumentError(f"{name} must be a non-empty string")
        return value.strip()

    def optional_string(self, name: str) -> str | None:
        value = self._pop_optional(name)
        if value is _MISSING:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ToolArgumentError(f"{name} must be a non-empty string")
        return value.strip()

    def integer(
        self,
        name: str,
        *,
        default: int | None = None,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        value = self._pop_optional(name)
        if value is _MISSING:
            if default is None:
                raise ToolArgumentError(f"{name} is required")
            parsed = default
        elif not isinstance(value, int) or isinstance(value, bool):
            raise ToolArgumentError(f"{name} must be an integer")
        else:
            parsed = value

        if minimum is not None and parsed < minimum:
            raise ToolArgumentError(f"{name} must be at least {minimum}")
        if maximum is not None and parsed > maximum:
            raise ToolArgumentError(f"{name} must be at most {maximum}")
        return parsed

    def boolean(self, name: str, *, default: bool) -> bool:
        value = self._pop_optional(name)
        if value is _MISSING:
            return default
        if not isinstance(value, bool):
            raise ToolArgumentError(f"{name} must be a boolean")
        return value

    def uuid(self, name: str, *, required: bool = True) -> UUID | None:
        raw_value = self._pop_required(name) if required else self._pop_optional(name)
        if raw_value is _MISSING:
            return None
        if not isinstance(raw_value, str):
            raise ToolArgumentError(f"{name} must be a UUID string")
        try:
            return UUID(raw_value)
        except ValueError as error:
            raise ToolArgumentError(f"{name} must be a valid UUID") from error

    def date(self, name: str) -> date:
        raw_value = self.required_string(name)
        try:
            return date.fromisoformat(raw_value)
        except ValueError as error:
            raise ToolArgumentError(f"{name} must be an ISO 8601 date") from error

    def datetime(self, name: str) -> datetime:
        raw_value = self.required_string(name)
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError as error:
            raise ToolArgumentError(
                f"{name} must be an ISO 8601 datetime with a UTC offset"
            ) from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ToolArgumentError(f"{name} must include a UTC offset")
        return parsed

    def choice(
        self,
        name: str,
        choices: frozenset[str],
        *,
        required: bool = False,
    ) -> str | None:
        value = self.required_string(name) if required else self.optional_string(name)
        if value is not None and value not in choices:
            allowed = ", ".join(sorted(choices))
            raise ToolArgumentError(f"{name} must be one of: {allowed}")
        return value

    def finish(self) -> None:
        if self._values:
            names = ", ".join(sorted(self._values))
            raise ToolArgumentError(f"unexpected arguments: {names}")

    def _pop_required(self, name: str) -> object:
        value = self._values.pop(name, _MISSING)
        if value is _MISSING:
            raise ToolArgumentError(f"{name} is required")
        return value

    def _pop_optional(self, name: str) -> object:
        return self._values.pop(name, _MISSING)
