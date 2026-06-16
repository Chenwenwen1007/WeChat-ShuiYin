from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "short-video-parser"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_base_url: str = "http://127.0.0.1:8000"
    cors_origins: List[str] | str = ["*"]
    http_timeout: float = 20.0
    download_timeout: float = 120.0
    log_level: str = "INFO"

    # 第三方去水印API配置（可选）
    third_party_api_url: str = ""
    third_party_api_key: str = ""
    third_party_api_timeout: float = 30.0
    
    # bugpk.com免费API配置（默认启用）
    bugpk_api_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, list):
            return value
        if value == "*":
            return ["*"]
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
