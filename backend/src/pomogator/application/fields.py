"""Read and upsert per-user interactive field states."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.domain.fields import (
    annotate_document_fields,
    default_field_values,
    normalize_field_value,
)
from pomogator.infrastructure.db.models import FieldStateModel, PageModel


async def load_field_states(
    session: AsyncSession, *, user_id: UUID, page: PageModel
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    document, specs = annotate_document_fields(page.document)
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
    _, specs = annotate_document_fields(page.document)
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
