from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CountrySource(BaseModel):
    page_id: str
    slug: str
    flag: str = "🌍"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_domain: str = "localhost"
    database_url: str = "postgresql+asyncpg://pomogator:pomogator@localhost:5432/pomogator"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str = ""
    telegram_webapp_url: str = "http://localhost:5173"
    socks_enabled: bool = False
    telegram_socks_proxy_list_url: str = (
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"
    )
    telegram_socks_cache_ttl_seconds: int = 300
    telegram_socks_probe_timeout_seconds: float = 10.0
    telegram_socks_max_acquire_attempts: int = 12
    notion_token: str = ""
    notion_countries: list[CountrySource] = Field(default_factory=list)
    admin_telegram_ids: list[int] = Field(default_factory=list)
    sync_interval_minutes: int = 60
    init_data_max_age_seconds: int = 3600
    payment_provider: Literal["stub"] = "stub"
    allow_stub_payments_in_production: bool = False
    telegram_clock_skew_seconds: int = 30
    pdf_trace_secret: str = ""

    @model_validator(mode="after")
    def validate_runtime(self) -> "Settings":
        if self.app_env != "production":
            return self
        required = {
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "NOTION_TOKEN": self.notion_token,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing production secrets: {', '.join(missing)}")
        if not self.telegram_webapp_url.startswith("https://"):
            raise ValueError("TELEGRAM_WEBAPP_URL must use HTTPS in production")
        if not self.notion_countries:
            raise ValueError("At least one Notion country is required in production")
        if self.payment_provider == "stub" and not self.allow_stub_payments_in_production:
            raise ValueError("Stub payments are disabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
