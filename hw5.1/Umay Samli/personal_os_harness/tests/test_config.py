from pathlib import Path

import pytest

from personal_os.config import ConfigurationError, Settings


def test_settings_parse_typed_values_without_loading_an_env_file() -> None:
    settings = Settings.from_environment(
        {
            "OLLAMA_MODEL": "qwen3:8b",
            "OLLAMA_TIMEOUT_SECONDS": "45",
            "OLLAMA_MAX_TOOL_ROUNDS": "4",
            "PLANNING_DATABASE_URL": "postgresql://planning",
            "SCHEDULING_RESOLUTION_MINUTES": "15",
            "DAILY_PROFILE_COMPLETE_DEFAULT": "true",
            "DEADLINE_BUFFER_MINUTES": "0",
            "REMINDER_DISPLAY_LIMIT": "3",
            "EXTERNAL_TIMEOUT_SECONDS": "9",
            "EXTERNAL_MAX_RESPONSE_BYTES": "2048",
            "EXTERNAL_MAX_TEXT_CHARACTERS": "512",
        },
        env_file=Path("unused"),
    )

    assert settings.ollama.model == "qwen3:8b"
    assert settings.ollama.timeout_seconds == 45
    assert settings.ollama.max_tool_rounds == 4
    assert settings.databases.planning_url == "postgresql://planning"
    assert settings.databases.memory_url is None
    assert settings.planning.daily_profile_complete_default is True
    assert settings.planning.deadline_buffer_minutes == 0
    assert settings.planning.reminder_display_limit == 3
    assert settings.external_context.timeout_seconds == 9
    assert settings.external_context.maximum_response_bytes == 2048
    assert settings.external_context.maximum_text_characters == 512


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("OLLAMA_TIMEOUT_SECONDS", "0"),
        ("OLLAMA_MAX_TOOL_ROUNDS", "many"),
        ("PROPOSAL_TTL_MINUTES", "-1"),
        ("REMINDER_DISPLAY_LIMIT", "0"),
        ("DEADLINE_BUFFER_MINUTES", "-1"),
        ("DAILY_PROFILE_COMPLETE_DEFAULT", "sometimes"),
        ("EXTERNAL_MAX_RESPONSE_BYTES", "0"),
        ("WEATHER_FORECAST_URL", "file:///tmp/weather"),
    ],
)
def test_settings_reject_invalid_positive_integers(name: str, value: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_environment({name: value}, env_file=Path("unused"))


def test_public_summary_does_not_expose_database_urls() -> None:
    settings = Settings.from_environment(
        {
            "PLANNING_DATABASE_URL": "postgresql://user:secret@localhost/planning",
            "MEMORY_DATABASE_URL": "postgresql://user:secret@localhost/memory",
        },
        env_file=Path("unused"),
    )

    summary = settings.public_summary()

    assert summary["planning_database_configured"] is True
    assert summary["memory_database_configured"] is True
    assert summary["weather_forecast_url"] == "https://api.open-meteo.com/v1/forecast"
    assert "secret" not in repr(summary)
