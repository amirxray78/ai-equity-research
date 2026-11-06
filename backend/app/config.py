from pathlib import Path
from typing import Annotated

from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    SUPABASE_URL: AnyHttpUrl
    SUPABASE_ANON_KEY: SecretStr = Field(min_length=1)
    SUPABASE_SERVICE_ROLE_KEY: SecretStr = Field(min_length=1)
    DATABASE_URL: PostgresDsn = Field(repr=False)
    OPENAI_API_KEY: SecretStr = Field(min_length=1)
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", min_length=1)
    OPENAI_EMBEDDING_DIMENSIONS: int = Field(default=1536, gt=0)
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = Field(min_length=1)

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_allowed_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            url = AnyHttpUrl(origin)
            if (
                url.username
                or url.password
                or url.path not in (None, "/")
                or url.query
                or url.fragment
            ):
                raise ValueError(
                    "ALLOWED_ORIGINS must contain HTTP origins without paths or credentials"
                )
        return [origin.rstrip("/") for origin in origins]


settings = Settings()
