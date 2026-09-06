"""User-triggered Notion country sync (Celery) + status."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.config import get_settings
from pomogator.infrastructure.db.models import CountryModel, SyncRunModel

_RUNNING_STALE = timedelta(minutes=20)


def country_source_exists(slug: str) -> bool:
    return any(source.slug == slug for source in get_settings().notion_countries)


async def latest_sync_run(
    session: AsyncSession, *, country_id: UUID
) -> SyncRunModel | None:
    result = await session.scalar(
        select(SyncRunModel)
        .where(SyncRunModel.country_id == country_id)
        .order_by(SyncRunModel.started_at.desc())
        .limit(1)
    )
    return result if isinstance(result, SyncRunModel) else None


def sync_status_payload(
    country: CountryModel, run: SyncRunModel | None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slug": country.slug,
        "content_version": country.content_version,
        "status": "idle",
        "error": None,
        "started_at": None,
        "finished_at": None,
    }
    if run is None:
        return payload
    payload["status"] = run.status
    payload["error"] = run.error
    payload["started_at"] = run.started_at.isoformat() if run.started_at else None
    payload["finished_at"] = run.finished_at.isoformat() if run.finished_at else None
    return payload


def _is_active_run(run: SyncRunModel | None, *, now: datetime) -> bool:
    if run is None or run.status != "running":
        return False
    started = run.started_at
    if started is None:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return now - started < _RUNNING_STALE


async def request_country_sync(
    session: AsyncSession, *, country: CountryModel
) -> dict[str, Any]:
    """Enqueue Celery sync unless a fresh run is already in progress."""
    if not country_source_exists(country.slug):
        raise KeyError(country.slug)

    run = await latest_sync_run(session, country_id=country.id)
    now = datetime.now(UTC)
    if _is_active_run(run, now=now):
        payload = sync_status_payload(country, run)
        payload["accepted"] = False
        payload["queued"] = False
        return payload

    Celery(broker=get_settings().redis_url).send_task(
        "pomogator.sync_country", args=[country.slug]
    )
    payload = sync_status_payload(country, run)
    # Reflect intent until the worker creates a new SyncRun row.
    payload["status"] = "queued"
    payload["accepted"] = True
    payload["queued"] = True
    return payload
