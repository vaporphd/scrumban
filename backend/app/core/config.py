from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    url: str = "postgresql+asyncpg://scrumban:scrumban@localhost:5432/scrumban"
    echo: bool = False
    pool_size: int = 10


class RedisSettings(BaseSettings):
    url: str = "redis://localhost:6379/0"


class JWTSettings(BaseSettings):
    secret: str = "change-me-in-prod"
    algorithm: str = "HS256"
    access_ttl_minutes: int = 30
    refresh_ttl_days: int = 30


class TelegramSettings(BaseSettings):
    bot_token: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""
    mode: Literal["polling", "webhook"] = "polling"


class StorageSettings(BaseSettings):
    endpoint_url: str = "http://localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "attachments"
    region: str = "us-east-1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
