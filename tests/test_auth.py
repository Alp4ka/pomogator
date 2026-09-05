import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from pomogator.config import get_settings
from pomogator.presentation.api.auth import validate_init_data


def signed_init_data(bot_token: str, auth_date: int | None = None) -> str:
    values = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "test-query",
        "user": json.dumps({"id": 42, "first_name": "Test"}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_init_data(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()
    assert validate_init_data(signed_init_data("test-token")).id == 42
    get_settings.cache_clear()


def test_tampered_init_data_is_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as error:
        validate_init_data(signed_init_data("other-token"))
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_expired_init_data_is_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("INIT_DATA_MAX_AGE_SECONDS", "10")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as error:
        validate_init_data(signed_init_data("test-token", int(time.time()) - 60))
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_future_init_data_is_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CLOCK_SKEW_SECONDS", "5")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as error:
        validate_init_data(signed_init_data("test-token", int(time.time()) + 60))
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_empty_token_cannot_authenticate(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as error:
        validate_init_data("auth_date=1&hash=anything&user={}")
    assert error.value.status_code == 503
    get_settings.cache_clear()
