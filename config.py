"""
Centralized configuration. Reads from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    default_repo_path: str = "."
    churn_lookback_commits: int = 1000
    max_files_per_scan: int = 2000


    weight_churn: float = 0.4
    weight_complexity: float = 0.4
    weight_markers: float = 0.2


@lru_cache
def get_settings() -> Settings:
    return Settings()
