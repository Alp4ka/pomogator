import pytest
from pomogator.config import Settings
from pydantic import ValidationError


def test_production_rejects_missing_secrets():
    with pytest.raises(ValidationError):
        Settings(app_env="production")


def test_production_rejects_stub_by_default():
    with pytest.raises(ValidationError, match="Stub payments"):
        Settings(
            app_env="production",
            app_domain="example.com",
            telegram_bot_token="token",
            telegram_webhook_secret="secret",
            telegram_webapp_url="https://example.com",
            notion_token="notion",
            notion_countries=[{"page_id": "a" * 32, "slug": "test"}],
        )
