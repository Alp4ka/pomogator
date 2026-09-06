"""Create forensically stamped PDF exports for readable pages."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.config import get_settings
from pomogator.domain.pdf_trace import derive_trace_secret, new_export_id, seal_trace
from pomogator.infrastructure.db.models import PdfExportModel, UserModel
from pomogator.infrastructure.pdf.render import filename_for_title, render_page_pdf


async def export_page_pdf(
    session: AsyncSession,
    *,
    user: UserModel,
    page_id: UUID,
    country_id: UUID,
    title: str,
    document: list[dict[str, Any]],
    entitled: bool,
) -> tuple[bytes, str, UUID]:
    settings = get_settings()
    secret_source = settings.pdf_trace_secret or settings.telegram_bot_token
    secret = derive_trace_secret(secret_source)
    export_id = new_export_id()
    issued_at = datetime.now(UTC)
    payload = {
        "v": 1,
        "eid": str(export_id),
        "uid": str(user.id),
        "tg": user.telegram_id,
        "pid": str(page_id),
        "cid": str(country_id),
        "ent": bool(entitled),
        "ts": int(issued_at.timestamp()),
    }
    sealed = seal_trace(secret, payload)
    session.add(
        PdfExportModel(
            id=export_id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            page_id=page_id,
            country_id=country_id,
            entitled=entitled,
            seal=sealed,
        )
    )
    await session.commit()
    pdf_bytes = render_page_pdf(
        title=title,
        document=document,
        export_id=export_id,
        sealed_token=sealed,
    )
    return pdf_bytes, filename_for_title(title), export_id
