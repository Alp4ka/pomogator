"""Short-lived public PDF download links for Telegram Mini App."""

from __future__ import annotations

import base64
import json
import secrets
from typing import Any

from redis.asyncio import Redis

_KEY = "pomogator:pdf-dl:{token}"
_TTL_SECONDS = 120


async def store_pdf_download(
    redis: Redis, *, pdf_bytes: bytes, filename: str
) -> str:
    token = secrets.token_urlsafe(24)
    payload = json.dumps(
        {
            "filename": filename,
            "data": base64.b64encode(pdf_bytes).decode("ascii"),
        },
        separators=(",", ":"),
    )
    await redis.setex(_KEY.format(token=token), _TTL_SECONDS, payload)
    return token


async def pop_pdf_download(redis: Redis, token: str) -> tuple[bytes, str] | None:
    key = _KEY.format(token=token)
    raw = await redis.get(key)
    if raw is None:
        return None
    await redis.delete(key)
    try:
        payload: dict[str, Any] = json.loads(raw)
        data = base64.b64decode(str(payload["data"]), validate=True)
        filename = str(payload.get("filename") or "guide.pdf")
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return data, filename
