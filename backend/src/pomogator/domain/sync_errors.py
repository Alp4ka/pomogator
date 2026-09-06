"""User-facing Notion sync errors (never expose raw HTTP/URLs)."""

from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

USER_SYNC_FAILED = "Не удалось обновить материалы. Попробуйте позже."
USER_SYNC_RATE_LIMITED = (
    "Слишком много запросов к источнику материалов. Подождите пару минут и попробуйте снова."
)
USER_SYNC_UNAVAILABLE = "Источник материалов временно недоступен. Попробуйте позже."


class NotionSyncError(Exception):
    """Controlled sync failure with a stable public code."""

    def __init__(self, code: str, *, public_message: str | None = None) -> None:
        self.code = code
        self.public_message = public_message or public_sync_message(code)
        super().__init__(self.public_message)


def public_sync_message(code: str) -> str:
    if code == "rate_limited":
        return USER_SYNC_RATE_LIMITED
    if code in {"unavailable", "timeout"}:
        return USER_SYNC_UNAVAILABLE
    return USER_SYNC_FAILED


def user_facing_sync_error(exc: BaseException) -> str:
    """Map any sync exception to a safe message for Telegram / Mini App."""
    if isinstance(exc, NotionSyncError):
        return exc.public_message

    text = str(exc)
    lowered = text.casefold()
    if "429" in lowered or "too many requests" in lowered or "rate limit" in lowered:
        return USER_SYNC_RATE_LIMITED
    if any(token in lowered for token in ("timeout", "timed out", "connect", "503", "502", "504")):
        return USER_SYNC_UNAVAILABLE
    if _URL_RE.search(text) or "api.notion.com" in lowered or "traceback" in lowered:
        return USER_SYNC_FAILED
    # Still avoid leaking unexpected internals.
    return USER_SYNC_FAILED
