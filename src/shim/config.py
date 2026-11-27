from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment (or a local .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLAlchemy URL. Defaults to a local SQLite file so the broker and the test
    # suite run with no Postgres; production uses a postgresql+psycopg:// URL.
    database_url: str = Field(default="sqlite+pysqlite:///./shim.sqlite", alias="DATABASE_URL")

    # A holding whose owning app has not reported within this window is flagged
    # "stale" by the reconciler. It is an observation only — nothing is moved.
    heartbeat_stale_seconds: int = Field(default=90, alias="SHIM_HEARTBEAT_STALE_SECONDS")


def get_settings() -> Settings:
    # Instantiated per call so tests can override the environment.
    return Settings()  # type: ignore[call-arg]
