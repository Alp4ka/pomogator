from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.config import get_settings
from pomogator.domain.content import AccessLevel
from pomogator.domain.payments import PaymentProvider, StubPaymentProvider
from pomogator.infrastructure.db.base import session_dependency
from pomogator.infrastructure.db.models import (
    EntitlementModel,
    ImageModel,
    PageImageModel,
    PageModel,
    PaymentModel,
    UserModel,
)
from pomogator.infrastructure.db.repositories import ContentRepository
from pomogator.presentation.api.auth import TelegramIdentity, telegram_identity

router = APIRouter(prefix="/api")


@dataclass(slots=True)
class RequestContext:
    session: AsyncSession
    repo: ContentRepository
    user: UserModel


async def context(
    identity: Annotated[TelegramIdentity, Depends(telegram_identity)],
    session: Annotated[AsyncSession, Depends(session_dependency)],
) -> RequestContext:
    repo = ContentRepository(session)
    user = await repo.upsert_user(identity.id, identity.first_name, identity.username)
    await session.commit()
    return RequestContext(session, repo, user)


Context = Annotated[RequestContext, Depends(context)]


@router.get("/countries")
async def countries(ctx: Context) -> list[dict[str, object]]:
    repo, user = ctx.repo, ctx.user
    return [
        {
            "slug": c.slug,
            "title": c.title,
            "flag": c.flag,
            "paid": await repo.entitled(user.id, c.id),
        }
        for c in await repo.countries()
    ]


@router.get("/countries/{slug}")
async def country(slug: str, ctx: Context) -> dict[str, object]:
    repo, user = ctx.repo, ctx.user
    item = await repo.country_by_slug(slug)
    if not item:
        raise HTTPException(404, "Country not found")
    root = await repo.root_page(item.id)
    return {
        "slug": item.slug,
        "title": item.title,
        "flag": item.flag,
        "root_page_id": str(root.id) if root else None,
        "paid": await repo.entitled(user.id, item.id),
    }


@router.get("/pages/{page_id}")
async def page(page_id: UUID, ctx: Context) -> dict[str, object]:
    repo, user = ctx.repo, ctx.user
    item = await repo.page(page_id)
    if not item or item.archived:
        raise HTTPException(404, "Page not found")
    paid = await repo.entitled(user.id, item.country_id)
    if item.access_level == AccessLevel.PAID and not paid:
        raise HTTPException(402, "Country access required")
    children = await repo.children(item.country_id, item.id)
    return {
        "id": str(item.id),
        "title": item.title,
        "document": item.document,
        "children": [
            {
                "id": str(x.id),
                "title": x.title,
                "locked": x.access_level == AccessLevel.PAID and not paid,
            }
            for x in children
        ],
    }


@router.post("/countries/{slug}/purchase")
async def purchase(slug: str, ctx: Context, request: Request) -> dict[str, str]:
    session, repo, user = ctx.session, ctx.repo, ctx.user
    country = await repo.country_by_slug(slug)
    if not country:
        raise HTTPException(404, "Country not found")
    supplied_key = request.headers.get("Idempotency-Key")
    key = supplied_key or f"stub:{user.id}:{country.id}"
    payment = await session.scalar(select(PaymentModel).where(PaymentModel.idempotency_key == key))
    provider: PaymentProvider = StubPaymentProvider()
    result = await provider.purchase(user.id, country.id, key)
    if payment is None:
        session.add(
            PaymentModel(
                idempotency_key=key,
                external_id=result.external_id,
                user_id=user.id,
                country_id=country.id,
                status="succeeded" if result.succeeded else "failed",
            )
        )
    if not result.succeeded:
        raise HTTPException(502, "Payment was not completed")
    Celery(broker=get_settings().redis_url).send_task("pomogator.sync_country", args=[country.slug])
    entitlement = await session.scalar(
        select(EntitlementModel).where(
            EntitlementModel.user_id == user.id, EntitlementModel.country_id == country.id
        )
    )
    if entitlement is None:
        session.add(EntitlementModel(user_id=user.id, country_id=country.id, active=True))
    else:
        entitlement.active = True
    await session.commit()
    return {"status": "succeeded", "provider": "stub"}


@router.get("/images/{digest}")
async def image(digest: str, ctx: Context) -> Response:
    session, user = ctx.session, ctx.user
    item = await session.scalar(select(ImageModel).where(ImageModel.sha256 == digest))
    if not item:
        raise HTTPException(404, "Image not found")
    pages = list(
        await session.scalars(
            select(PageModel)
            .join(PageImageModel, PageImageModel.page_id == PageModel.id)
            .where(PageImageModel.image_id == item.id, PageModel.archived.is_(False))
        )
    )
    allowed = False
    repo = ContentRepository(session)
    for page in pages:
        if page.access_level == AccessLevel.FREE or await repo.entitled(user.id, page.country_id):
            allowed = True
            break
    if not allowed:
        raise HTTPException(404, "Image not found")
    return Response(
        item.data,
        media_type=item.mime_type,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
