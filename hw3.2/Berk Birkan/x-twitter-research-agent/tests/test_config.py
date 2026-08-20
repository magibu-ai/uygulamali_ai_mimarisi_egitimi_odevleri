from x_research_agent.config import Settings


def test_neon_postgresql_url_uses_psycopg_driver():
    settings = Settings(
        database_url="postgresql://user:password@example.test/db?sslmode=require",
        _env_file=None,
    )

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.database_url
