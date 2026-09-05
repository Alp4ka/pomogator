import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException
from pydantic import BaseModel

from pomogator.config import get_settings


class TelegramIdentity(BaseModel):
    id: int
    first_name: str
    username: str | None = None


def validate_init_data(value: str) -> TelegramIdentity:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(503, "Telegram authentication is not configured")
    pairs = parse_qsl(value, keep_blank_values=True)
    if len({key for key, _ in pairs}) != len(pairs):
        raise HTTPException(401, "Duplicate Telegram fields")
    data = dict(pairs)
    received = data.pop("hash", "")
    check = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(received, expected):
        raise HTTPException(401, "Invalid Telegram signature")
    try:
        auth_date = datetime.fromtimestamp(int(data["auth_date"]), UTC)
    except (KeyError, ValueError, OverflowError, OSError):
        raise HTTPException(401, "Invalid auth date") from None
    age = (datetime.now(UTC) - auth_date).total_seconds()
    if age < -settings.telegram_clock_skew_seconds:
        raise HTTPException(401, "Telegram auth date is in the future")
    if age > settings.init_data_max_age_seconds:
        raise HTTPException(401, "Telegram session expired")
    try:
        return TelegramIdentity.model_validate(json.loads(data["user"]))
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, "Invalid Telegram user") from None


async def telegram_identity(
    authorization: Annotated[str, Header()] = "",
) -> TelegramIdentity:
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "tma" or not value:
        raise HTTPException(401, "Telegram initData required")
    return validate_init_data(value)
