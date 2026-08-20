from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/x_research"
    app_env: str = "development"
    log_level: str = "INFO"
    research_retention_days: int = Field(default=7, ge=1, le=30)
    openrouter_app_url: str = "http://localhost:7860"
    openrouter_app_name: str = "X/Twitter Research Agent"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    xquik_base_url: str = "https://xquik.com/api/v1"
    max_agent_steps: int = Field(default=8, ge=2, le=12)
    max_search_calls: int = Field(default=6, ge=1, le=10)
    request_timeout_seconds: float = Field(default=30.0, ge=5, le=120)

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Accept Neon-style URLs while explicitly selecting psycopg 3."""
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
