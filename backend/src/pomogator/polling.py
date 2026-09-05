"""Telegram long-polling process with optional SOCKS5 failover."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

from pomogator.config import get_settings
from pomogator.infrastructure.telegram.socks_pool import (
    TELEGRAM_PROBE_URL,
    SocksProxyPool,
    https_reachable,
    resolve_socks_proxy,
)
from pomogator.presentation.bot.handlers import dispatcher

log = logging.getLogger(__name__)

HEALTH_INTERVAL_SECONDS = 25.0
HEALTH_FAILURE_THRESHOLD = 3


async def _watch_telegram_health(bot: Bot, stop: asyncio.Event) -> None:
    failures = 0
    while not stop.is_set():
        try:
            await asyncio.wait_for(bot.get_me(), timeout=15.0)
            failures = 0
        except Exception as exc:  # noqa: BLE001 — any transport failure triggers rotation
            failures += 1
            log.warning(
                "Telegram health check failed (%s/%s): %s",
                failures,
                HEALTH_FAILURE_THRESHOLD,
                exc,
            )
            if failures >= HEALTH_FAILURE_THRESHOLD:
                stop.set()
                return
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEALTH_INTERVAL_SECONDS)
        except TimeoutError:
            continue


async def _run_polling(bot: Bot, proxy_url: str | None) -> None:
    dp = dispatcher()
    stop = asyncio.Event()
    watcher = asyncio.create_task(_watch_telegram_health(bot, stop), name="telegram-health")

    async def _stop_on_health_failure() -> None:
        await stop.wait()
        log.warning("Stopping polling to rotate Telegram transport")
        await dp.stop_polling()

    stopper = asyncio.create_task(_stop_on_health_failure(), name="telegram-stopper")
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        me = await bot.get_me()
        log.info(
            "Long polling started for @%s via %s",
            me.username,
            proxy_url or "direct",
        )
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            close_bot_session=False,
            handle_signals=False,
        )
    finally:
        stop.set()
        watcher.cancel()
        stopper.cancel()
        await asyncio.gather(watcher, stopper, return_exceptions=True)


async def run() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for long polling")

    pool = SocksProxyPool(
        settings.telegram_socks_proxy_list_url,
        cache_ttl_seconds=settings.telegram_socks_cache_ttl_seconds,
        probe_timeout=settings.telegram_socks_probe_timeout_seconds,
        max_acquire_attempts=settings.telegram_socks_max_acquire_attempts,
    )
    proxy_url = await resolve_socks_proxy(pool, probe_url=TELEGRAM_PROBE_URL, label="Telegram")

    while True:
        session = AiohttpSession(proxy=proxy_url) if proxy_url else AiohttpSession()
        bot = Bot(settings.telegram_bot_token, session=session)
        try:
            if proxy_url and not await https_reachable(
                TELEGRAM_PROBE_URL, proxy_url, timeout_seconds=pool.probe_timeout
            ):
                pool.mark_failed(proxy_url)
                proxy_url = await pool.acquire(probe_url=TELEGRAM_PROBE_URL)
                continue
            await _run_polling(bot, proxy_url)
        except TelegramNetworkError as exc:
            log.warning("Telegram network error: %s", exc)
        except Exception:
            log.exception("Polling crashed; will rotate transport and retry")
        finally:
            await bot.session.close()

        if proxy_url:
            pool.mark_failed(proxy_url)
        else:
            log.warning("Direct Telegram path failed; switching to SOCKS5")
        try:
            proxy_url = await pool.acquire(probe_url=TELEGRAM_PROBE_URL)
        except Exception:
            log.exception("Unable to acquire SOCKS5 proxy; retrying soon")
            proxy_url = None
            await asyncio.sleep(5.0)
            proxy_url = await resolve_socks_proxy(
                pool, probe_url=TELEGRAM_PROBE_URL, label="Telegram"
            )
            if proxy_url is None and not await https_reachable(TELEGRAM_PROBE_URL, None):
                await asyncio.sleep(15.0)
                continue
        await asyncio.sleep(1.0)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
