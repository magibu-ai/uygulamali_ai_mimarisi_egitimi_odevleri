"""Typed environment configuration with safe public rendering."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / "configs" / ".env"


class ConfigurationError(ValueError):
    """Raised when application configuration is invalid."""


@dataclass(frozen=True, slots=True)
class OllamaSettings:
    """Connection and orchestration limits for the local Ollama provider."""

    model: str
    url: str
    timeout_seconds: int
    max_tool_rounds: int


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Independent connection URLs for planning and memory storage."""

    planning_url: str | None
    memory_url: str | None


@dataclass(frozen=True, slots=True)
class ExternalContextSettings:
    """Limits and endpoints for read-only external context providers."""

    timeout_seconds: int
    maximum_response_bytes: int
    maximum_text_characters: int
    weather_geocoding_url: str
    weather_forecast_url: str


@dataclass(frozen=True, slots=True)
class PlanningSettings:
    """Deterministic planning defaults loaded from the environment."""

    timezone: str
    scheduling_resolution_minutes: int
    fallback_personal_reserve_minutes: int
    daily_profile_complete_default: bool
    deadline_buffer_minutes: int
    proposal_ttl_minutes: int
    reminder_display_limit: int


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated application configuration assembled at startup."""

    ollama: OllamaSettings
    databases: DatabaseSettings
    external_context: ExternalContextSettings
    planning: PlanningSettings

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        env_file: Path = DEFAULT_ENV_FILE,
    ) -> Settings:
        if environment is None:
            load_dotenv(env_file, override=False)
            environment = os.environ

        ollama_url = _non_empty(
            environment.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat"),
            "OLLAMA_URL",
        )
        _validate_http_url(ollama_url, "OLLAMA_URL")

        return cls(
            ollama=OllamaSettings(
                model=_non_empty(environment.get("OLLAMA_MODEL", "llama3.1:8b"), "OLLAMA_MODEL"),
                url=ollama_url,
                timeout_seconds=_positive_int(environment, "OLLAMA_TIMEOUT_SECONDS", 120),
                max_tool_rounds=_positive_int(environment, "OLLAMA_MAX_TOOL_ROUNDS", 10),
            ),
            databases=DatabaseSettings(
                planning_url=_optional_non_empty(environment.get("PLANNING_DATABASE_URL")),
                memory_url=_optional_non_empty(environment.get("MEMORY_DATABASE_URL")),
            ),
            external_context=ExternalContextSettings(
                timeout_seconds=_positive_int(environment, "EXTERNAL_TIMEOUT_SECONDS", 15),
                maximum_response_bytes=_positive_int(
                    environment, "EXTERNAL_MAX_RESPONSE_BYTES", 1_000_000
                ),
                maximum_text_characters=_positive_int(
                    environment, "EXTERNAL_MAX_TEXT_CHARACTERS", 20_000
                ),
                weather_geocoding_url=_http_url(
                    environment.get(
                        "WEATHER_GEOCODING_URL",
                        "https://geocoding-api.open-meteo.com/v1/search",
                    ),
                    "WEATHER_GEOCODING_URL",
                ),
                weather_forecast_url=_http_url(
                    environment.get(
                        "WEATHER_FORECAST_URL",
                        "https://api.open-meteo.com/v1/forecast",
                    ),
                    "WEATHER_FORECAST_URL",
                ),
            ),
            planning=PlanningSettings(
                timezone=_non_empty(
                    environment.get("PLANNING_TIMEZONE", "Europe/Istanbul"),
                    "PLANNING_TIMEZONE",
                ),
                scheduling_resolution_minutes=_positive_int(
                    environment, "SCHEDULING_RESOLUTION_MINUTES", 15
                ),
                fallback_personal_reserve_minutes=_positive_int(
                    environment, "FALLBACK_PERSONAL_RESERVE_MINUTES", 720
                ),
                daily_profile_complete_default=_boolean(
                    environment, "DAILY_PROFILE_COMPLETE_DEFAULT", False
                ),
                deadline_buffer_minutes=_non_negative_int(
                    environment, "DEADLINE_BUFFER_MINUTES", 0
                ),
                proposal_ttl_minutes=_positive_int(environment, "PROPOSAL_TTL_MINUTES", 30),
                reminder_display_limit=_positive_int(environment, "REMINDER_DISPLAY_LIMIT", 5),
            ),
        )

    def public_summary(self) -> dict[str, str | int | bool]:
        """Return effective non-secret settings suitable for CLI output."""
        return {
            "ollama_model": self.ollama.model,
            "ollama_url": self.ollama.url,
            "ollama_timeout_seconds": self.ollama.timeout_seconds,
            "ollama_max_tool_rounds": self.ollama.max_tool_rounds,
            "planning_database_configured": self.databases.planning_url is not None,
            "memory_database_configured": self.databases.memory_url is not None,
            "external_timeout_seconds": self.external_context.timeout_seconds,
            "external_max_response_bytes": self.external_context.maximum_response_bytes,
            "external_max_text_characters": self.external_context.maximum_text_characters,
            "weather_geocoding_url": self.external_context.weather_geocoding_url,
            "weather_forecast_url": self.external_context.weather_forecast_url,
            "planning_timezone": self.planning.timezone,
            "scheduling_resolution_minutes": self.planning.scheduling_resolution_minutes,
            "fallback_personal_reserve_minutes": self.planning.fallback_personal_reserve_minutes,
            "daily_profile_complete_default": self.planning.daily_profile_complete_default,
            "deadline_buffer_minutes": self.planning.deadline_buffer_minutes,
            "proposal_ttl_minutes": self.planning.proposal_ttl_minutes,
            "reminder_display_limit": self.planning.reminder_display_limit,
        }


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    value = _integer(environment, name, default)
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


def _non_negative_int(environment: Mapping[str, str], name: str, default: int) -> int:
    value = _integer(environment, name, default)
    if value < 0:
        raise ConfigurationError(f"{name} cannot be negative")
    return value


def _integer(environment: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environment.get(name, str(default))
    try:
        return int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error


def _boolean(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environment.get(name, str(default)).strip().lower()
    if raw_value in {"true", "1", "yes"}:
        return True
    if raw_value in {"false", "0", "no"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


def _non_empty(value: str, name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ConfigurationError(f"{name} cannot be empty")
    return stripped


def _optional_non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_http_url(value: str, name: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError(f"{name} must be an HTTP(S) URL")


def _http_url(value: str, name: str) -> str:
    parsed = _non_empty(value, name)
    _validate_http_url(parsed, name)
    return parsed
