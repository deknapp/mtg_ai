"""Runtime configuration, loaded from environment variables / .env.

Secrets (the API key) are never hardcoded and never committed. See .env.example.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MTG_", env_file=".env", extra="ignore")

    # "mock" (default, zero-cost) or "anthropic".
    llm_backend: str = "mock"

    # Model routing. Cheap tier for narrow/high-volume steps; strong tier for reasoning/synthesis.
    model_cheap: str = "claude-haiku-4-5"
    model_strong: str = "claude-opus-4-8"

    # Local Scryfall SQLite database (built by the ingest step).
    db_path: str = "data/scryfall.sqlite"

    # 17Lands ratings cache (built/reloaded by the sealed ratings layer).
    ratings_db_path: str = "data/17lands.sqlite"

    # Default set to scope card + ratings data to. Marvel Super Heroes.
    default_set: str = "msh"

    # Where MTG Arena writes its player log (macOS default). The sealed importer auto-finds it.
    arena_log_path: str = "~/Library/Logs/Wizards Of The Coast/MTGA/Player.log"


class SecretSettings(BaseSettings):
    """Separated so the API key is only ever read from the environment, not MTG_-prefixed."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None


def get_settings() -> Settings:
    return Settings()


def get_secrets() -> SecretSettings:
    return SecretSettings()
