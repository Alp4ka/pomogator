"""Read and upsert per-user interactive field states."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.domain.fields import (
    FieldSpec,
    annotate_document_fields,
    default_field_values,
    normalize_field_value,
)
from pomogator.domain.links import remap_internal_links
from pomogator.infrastructure.db.models import FieldStateModel, PageModel


async def country_page_index(session: AsyncSession, country_id: UUID) -> dict[str, UUID]:
    rows = await session.execute(
        select(PageModel.notion_page_id, PageModel.id).where(
            PageModel.country_id == country_id,
            PageModel.archived.is_(False),
        )
    )
    return {notion_id: page_id for notion_id, page_id in rows.all()}


async def country_nav_index(session: AsyncSession, country_id: UUID) -> dict[str, UUID]:
    """Map nav_label → page id; first wins by position, then id."""
    rows = await session.execute(
        select(PageModel.nav_label, PageModel.id)
        .where(
            PageModel.country_id == country_id,
            PageModel.archived.is_(False),
            PageModel.nav_label.is_not(None),
        )
        .order_by(PageModel.position, PageModel.id)
    )
    index: dict[str, UUID] = {}
    for label, page_id in rows.all():
        if not label:
            continue
        key = str(label).casefold()
        if key not in index:
            index[key] = page_id
    return index


async def prepare_page_document(
    session: AsyncSession, page: PageModel
) -> tuple[list[dict[str, Any]], dict[str, FieldSpec]]:
    """Remap Notion internal links, annotate fields, resolve nav tags."""
    known = await country_page_index(session, page.country_id)
    page_nav = await country_nav_index(session, page.country_id)
    document = remap_internal_links(deepcopy(page.document), known)
    return annotate_document_fields(document, page_nav=page_nav)


async def load_field_states(
    session: AsyncSession, *, user_id: UUID, page: PageModel
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    document, specs = await prepare_page_document(session, page)
    defaults = default_field_values(specs)
    if not defaults:
        return document, {}

    rows = await session.scalars(
        select(FieldStateModel).where(
            FieldStateModel.user_id == user_id,
            FieldStateModel.page_id == page.id,
            FieldStateModel.field_key.in_(list(defaults)),
        )
    )
    saved = {row.field_key: row.value for row in rows}
    merged = {**defaults, **saved}
    return document, merged


async def set_field_state(
    session: AsyncSession,
    *,
    user_id: UUID,
    page: PageModel,
    field_key: str,
    value: str,
) -> dict[str, str]:
    _document, specs = await prepare_page_document(session, page)
    if field_key not in specs:
        raise KeyError(field_key)
    spec = specs[field_key]
    normalized = normalize_field_value(spec.kind, value)

    row = await session.scalar(
        select(FieldStateModel).where(
            FieldStateModel.user_id == user_id,
            FieldStateModel.page_id == page.id,
            FieldStateModel.field_key == field_key,
        )
    )
    if row is None:
        session.add(
            FieldStateModel(
                user_id=user_id,
                page_id=page.id,
                field_key=field_key,
                field_kind=spec.kind,
                value=normalized,
            )
        )
    else:
        if row.value == normalized:
            _, merged = await load_field_states(session, user_id=user_id, page=page)
            return merged
        row.value = normalized
        row.field_kind = spec.kind
    await session.commit()
    _, merged = await load_field_states(session, user_id=user_id, page=page)
    return merged
