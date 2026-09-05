import asyncio

from celery import Celery

from pomogator.application.sync import SyncCountry
from pomogator.config import get_settings
from pomogator.infrastructure.db.base import SessionFactory
from pomogator.infrastructure.notion.client import NotionClient

settings = get_settings()
celery = Celery("pomogator", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.beat_schedule = {
    "sync-countries": {
        "task": "pomogator.sync_all",
        "schedule": settings.sync_interval_minutes * 60,
    }
}


async def _sync_sources(slug: str | None = None) -> None:
    async with SessionFactory() as session:
        notion = NotionClient(settings.notion_token)
        try:
            service = SyncCountry(session, notion)
            for source in settings.notion_countries:
                if slug is None or source.slug == slug:
                    await service(source)
        finally:
            await notion.http.aclose()


@celery.task(name="pomogator.sync_all")  # type: ignore[untyped-decorator]
def sync_all() -> None:
    asyncio.run(_sync_sources())


@celery.task(name="pomogator.sync_country")  # type: ignore[untyped-decorator]
def sync_country(slug: str) -> None:
    asyncio.run(_sync_sources(slug))
