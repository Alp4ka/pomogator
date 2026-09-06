import asyncio
import logging

import httpx
from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pomogator.application.sync import SyncCountry
from pomogator.application.sync_waiters import pop_sync_waiters
from pomogator.config import Settings, get_settings
from pomogator.infrastructure.db.models import CountryModel
from pomogator.infrastructure.notion.client import NotionClient
from pomogator.infrastructure.telegram.notify import notify_country_sync_result
from pomogator.infrastructure.telegram.socks_pool import (
    NOTION_PROBE_URL,
    SocksProxyPool,
    resolve_socks_proxy,
)

log = logging.getLogger(__name__)

settings = get_settings()
celery = Celery("pomogator", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.beat_schedule = {
    "sync-countries": {
        "task": "pomogator.sync_all",
        "schedule": settings.sync_interval_minutes * 60,
    }
}


def _notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Accept": "application/json",
    }


def _socks_pool(cfg: Settings) -> SocksProxyPool:
    return SocksProxyPool(
        cfg.telegram_socks_proxy_list_url,
        cache_ttl_seconds=cfg.telegram_socks_cache_ttl_seconds,
        probe_timeout=cfg.telegram_socks_probe_timeout_seconds,
        max_acquire_attempts=cfg.telegram_socks_max_acquire_attempts,
    )


async def _notion_http_client(cfg: Settings) -> tuple[httpx.AsyncClient, str | None]:
    if not cfg.notion_token:
        raise RuntimeError("NOTION_TOKEN is required for sync")
    headers = _notion_headers(cfg.notion_token)
    proxy_url: str | None = None
    if cfg.socks_enabled:
        pool = _socks_pool(cfg)
        proxy_url = await resolve_socks_proxy(
            pool,
            probe_url=NOTION_PROBE_URL,
            headers=headers,
            label="Notion",
            enabled=True,
        )
    else:
        log.info("Notion SOCKS disabled; using direct connection")
    client = httpx.AsyncClient(
        proxy=proxy_url,
        timeout=60.0,
        follow_redirects=True,
    )
    log.info("Notion HTTP client using %s", proxy_url or "direct")
    return client, proxy_url


async def _notify_waiters(
    slug: str,
    *,
    title: str,
    flag: str,
    succeeded: bool,
    error: str | None = None,
) -> None:
    waiters = pop_sync_waiters(slug)
    if not waiters:
        return
    try:
        await notify_country_sync_result(
            waiters,
            slug=slug,
            title=title,
            flag=flag,
            succeeded=succeeded,
            error=error,
        )
    except Exception:
        log.exception("Failed to notify sync waiters for %s", slug)


async def _sync_sources(slug: str | None = None) -> None:
    cfg = get_settings()
    # Create engine inside the Celery task loop to avoid cross-loop asyncpg errors.
    engine = create_async_engine(cfg.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    http, _proxy = await _notion_http_client(cfg)
    try:
        async with session_factory() as session:
            notion = NotionClient(cfg.notion_token, http=http)
            service = SyncCountry(session, notion)
            for source in cfg.notion_countries:
                if slug is not None and source.slug != slug:
                    continue
                try:
                    await service(source)
                    country = await session.scalar(
                        select(CountryModel).where(CountryModel.slug == source.slug)
                    )
                    await _notify_waiters(
                        source.slug,
                        title=(country.title if country else source.slug.title()),
                        flag=(country.flag if country else source.flag),
                        succeeded=True,
                    )
                except Exception as exc:
                    await _notify_waiters(
                        source.slug,
                        title=source.slug.title(),
                        flag=source.flag,
                        succeeded=False,
                        error=str(exc),
                    )
                    raise
    finally:
        await http.aclose()
        await engine.dispose()


@celery.task(name="pomogator.sync_all")  # type: ignore[untyped-decorator]
def sync_all() -> None:
    asyncio.run(_sync_sources())


@celery.task(name="pomogator.sync_country")  # type: ignore[untyped-decorator]
def sync_country(slug: str) -> None:
    asyncio.run(_sync_sources(slug))
