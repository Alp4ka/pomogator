"""Redis waiters for country sync completion notifications."""

from __future__ import annotations

from typing import cast

import redis

from pomogator.config import get_settings

_KEY = "pomogator:sync:waiters:{slug}"
_TTL_SECONDS = 60 * 60


def _client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def register_sync_waiter(slug: str, telegram_id: int) -> None:
    client = _client()
    try:
        key = _KEY.format(slug=slug)
        client.sadd(key, str(telegram_id))
        client.expire(key, _TTL_SECONDS)
    finally:
        client.close()


def pop_sync_waiters(slug: str) -> list[int]:
    client = _client()
    try:
        key = _KEY.format(slug=slug)
        raw_members = client.smembers(key)
        members = cast(set[str], raw_members)
        if members:
            client.delete(key)
        return sorted({int(item) for item in members})
    finally:
        client.close()
