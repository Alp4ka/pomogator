"""One-shot Telegram messages from worker / bot helpers."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from pomogator.config import get_settings
from pomogator.infrastructure.telegram.socks_pool import (
    TELEGRAM_PROBE_URL,
    SocksProxyPool,
    resolve_socks_proxy,
)

log = logging.getLogger(__name__)


def country_ready_keyboard(slug: str) -> InlineKeyboardMarkup:
    settings = get_settings()
    url = f"{settings.telegram_webapp_url}?country={slug}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть путеводитель", web_app=WebAppInfo(url=url))],
            [InlineKeyboardButton(text="✦ Купить полный доступ", callback_data=f"buy:{slug}")],
            [InlineKeyboardButton(text="🌍 Другие страны", callback_data="showcountries")],
        ]
    )


def country_failed_keyboard(slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Повторить загрузку", callback_data=f"country:{slug}")],
            [InlineKeyboardButton(text="🌍 Другие страны", callback_data="showcountries")],
        ]
    )


async def _bot_session() -> tuple[Bot, str | None]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    proxy_url: str | None = None
    if settings.socks_enabled:
        pool = SocksProxyPool(
            settings.telegram_socks_proxy_list_url,
            cache_ttl_seconds=settings.telegram_socks_cache_ttl_seconds,
            probe_timeout=settings.telegram_socks_probe_timeout_seconds,
            max_acquire_attempts=settings.telegram_socks_max_acquire_attempts,
        )
        proxy_url = await resolve_socks_proxy(
            pool,
            probe_url=TELEGRAM_PROBE_URL,
            label="Telegram notify",
            enabled=True,
        )
    session = AiohttpSession(proxy=proxy_url) if proxy_url else AiohttpSession()
    return Bot(settings.telegram_bot_token, session=session), proxy_url


async def notify_country_sync_result(
    telegram_ids: list[int],
    *,
    slug: str,
    title: str,
    flag: str,
    succeeded: bool,
    error: str | None = None,
) -> None:
    if not telegram_ids:
        return
    label = f"{flag} {title}".strip() or slug
    if succeeded:
        text = (
            f"✅ <b>Путеводитель готов</b>\n\n"
            f"{label}\n"
            "Можно открывать материалы или оформить полный доступ."
        )
        markup = country_ready_keyboard(slug)
    else:
        detail = (error or "неизвестная ошибка")[:200]
        text = (
            f"⚠️ <b>Не удалось загрузить путеводитель</b>\n\n"
            f"{label}\n"
            f"<code>{detail}</code>\n\n"
            "Можно повторить загрузку."
        )
        markup = country_failed_keyboard(slug)

    bot, _proxy = await _bot_session()
    try:
        for chat_id in telegram_ids:
            try:
                await bot.send_message(
                    chat_id,
                    text,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
            except Exception:
                log.exception("Failed to notify telegram_id=%s about sync %s", chat_id, slug)
    finally:
        await bot.session.close()
