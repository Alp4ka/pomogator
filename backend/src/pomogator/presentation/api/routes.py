from dataclasses import dataclass
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.application.content_sync import (
    country_source_exists,
    latest_sync_run,
    request_country_sync,
    sync_status_payload,
)
from pomogator.application.fields import load_field_states, set_field_state
from pomogator.application.payments import PurchaseError, purchase_country_access
from pomogator.application.pdf_export import export_page_pdf
from pomogator.domain.content import AccessLevel
from pomogator.domain.fields import annotate_document_fields
from pomogator.infrastructure.db.base import session_dependency
from pomogator.infrastructure.db.models import (
    ImageModel,
    PageImageModel,
    PageModel,
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
    run = await latest_sync_run(ctx.session, country_id=item.id)
    return {
        "slug": item.slug,
        "title": item.title,
        "flag": item.flag,
        "root_page_id": str(root.id) if root else None,
        "paid": await repo.entitled(user.id, item.id),
        "content_version": item.content_version,
        "sync_status": run.status if run else "idle",
    }


@router.get("/countries/{slug}/sync")
async def country_sync_status(slug: str, ctx: Context) -> dict[str, object]:
    repo = ctx.repo
    item = await repo.country_by_slug(slug)
    if not item:
        raise HTTPException(404, "Country not found")
    if not country_source_exists(slug):
        raise HTTPException(404, "Country sync source not configured")
    run = await latest_sync_run(ctx.session, country_id=item.id)
    return sync_status_payload(item, run)


@router.post("/countries/{slug}/sync")
async def country_sync_start(slug: str, ctx: Context) -> dict[str, object]:
    repo = ctx.repo
    item = await repo.country_by_slug(slug)
    if not item:
        raise HTTPException(404, "Country not found")
    try:
        return await request_country_sync(ctx.session, country=item)
    except KeyError as exc:
        raise HTTPException(404, "Country sync source not configured") from exc


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
    document, fields = await load_field_states(ctx.session, user_id=user.id, page=item)
    return {
        "id": str(item.id),
        "title": item.title,
        "document": document,
        "fields": fields,
        "children": [
            {
                "id": str(x.id),
                "title": x.title,
                "locked": x.access_level == AccessLevel.PAID and not paid,
            }
            for x in children
        ],
    }


@router.put("/pages/{page_id}/fields/{field_key}")
async def page_field(
    page_id: UUID, field_key: str, ctx: Context, request: Request
) -> dict[str, object]:
    repo, user = ctx.repo, ctx.user
    item = await repo.page(page_id)
    if not item or item.archived:
        raise HTTPException(404, "Page not found")
    paid = await repo.entitled(user.id, item.country_id)
    if item.access_level == AccessLevel.PAID and not paid:
        raise HTTPException(402, "Country access required")
    body = await request.json()
    if not isinstance(body, dict) or "value" not in body:
        raise HTTPException(400, "Body must include string value")
    raw_value = body["value"]
    if not isinstance(raw_value, str):
        raise HTTPException(400, "value must be a string")
    try:
        fields = await set_field_state(
            ctx.session,
            user_id=user.id,
            page=item,
            field_key=field_key,
            value=raw_value,
        )
    except KeyError as exc:
        raise HTTPException(404, "Field not found") from exc
    return {"fields": fields}


@router.get("/pages/{page_id}/pdf")
async def page_pdf(page_id: UUID, ctx: Context) -> Response:
    repo, user = ctx.repo, ctx.user
    item = await repo.page(page_id)
    if not item or item.archived:
        raise HTTPException(404, "Page not found")
    paid = await repo.entitled(user.id, item.country_id)
    if item.access_level == AccessLevel.PAID and not paid:
        raise HTTPException(402, "Country access required")
    document, _fields = annotate_document_fields(item.document)
    pdf_bytes, filename, _export_id = await export_page_pdf(
        ctx.session,
        user=user,
        page_id=item.id,
        country_id=item.country_id,
        title=item.title,
        document=document,
        entitled=paid,
    )
    ascii_name = "guide.pdf"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "no-store",
        },
    )


@router.post("/countries/{slug}/purchase")
async def purchase(slug: str, ctx: Context, request: Request) -> dict[str, str]:
    session, repo, user = ctx.session, ctx.repo, ctx.user
    country = await repo.country_by_slug(slug)
    if not country:
        raise HTTPException(404, "Country not found")
    supplied_key = request.headers.get("Idempotency-Key")
    key = supplied_key or f"stub:{user.id}:{country.id}"
    try:
        return await purchase_country_access(
            session, user=user, country=country, idempotency_key=key
        )
    except PurchaseError as exc:
        raise HTTPException(502, str(exc)) from exc


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
        headers={"X-Content-Type-Options": "nosniff"},
    )
