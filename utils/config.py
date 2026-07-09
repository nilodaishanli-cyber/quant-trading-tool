from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "个人量化交易分析平台"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/quant_platform.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-before-production")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
    api_base_url: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "900"))


settings = Settings()
