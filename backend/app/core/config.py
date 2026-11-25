"""Application configuration powered by pydantic-settings."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CCI STEM Connect Impact Measurement API"
    app_version: str = "1.0.0"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = (
        "postgresql+psycopg2://cci_user:cci_password@localhost:5432/cci_stem_connect"
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Security & Privacy
    admin_api_key: str = "dev-cci-stem-admin-key"
    participant_lookup_mode: Literal["strict_generic", "trusted_direct"] = (
        "strict_generic"
    )
    default_phone_region: str = "NG"
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 120
    rate_limit_lookup_per_minute: int = 15
    rate_limit_submit_per_minute: int = 30

    # CORS
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Storage & Imports
    reports_storage_dir: Path = Path("./storage/reports")
    max_import_file_size_mb: int = 10

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, value: str) -> str:
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+psycopg2://", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+psycopg2://", 1)
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @property
    def max_import_file_bytes(self) -> int:
        return self.max_import_file_size_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
