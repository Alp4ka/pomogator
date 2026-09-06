from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.config import get_settings
from pomogator.domain.payments import PaymentProvider, StubPaymentProvider
from pomogator.infrastructure.db.models import (
    CountryModel,
    EntitlementModel,
    PaymentModel,
    UserModel,
)


class PurchaseError(Exception):
    def __init__(self, message: str, *, status: str = "failed") -> None:
        super().__init__(message)
        self.status = status


async def purchase_country_access(
    session: AsyncSession,
    *,
    user: UserModel,
    country: CountryModel,
    idempotency_key: str,
    provider: PaymentProvider | None = None,
    trigger_sync: bool = True,
) -> dict[str, str]:
    """Idempotent stub-ready purchase that grants country entitlement."""
    payment_provider = provider or StubPaymentProvider()
    existing = await session.scalar(
        select(PaymentModel).where(PaymentModel.idempotency_key == idempotency_key)
    )
    result = await payment_provider.purchase(user.id, country.id, idempotency_key)
    if existing is None:
        session.add(
            PaymentModel(
                idempotency_key=idempotency_key,
                external_id=result.external_id,
                user_id=user.id,
                country_id=country.id,
                status="succeeded" if result.succeeded else "failed",
            )
        )
    if not result.succeeded:
        await session.commit()
        raise PurchaseError("Payment was not completed", status="failed")

    entitlement = await session.scalar(
        select(EntitlementModel).where(
            EntitlementModel.user_id == user.id,
            EntitlementModel.country_id == country.id,
        )
    )
    if entitlement is None:
        session.add(EntitlementModel(user_id=user.id, country_id=country.id, active=True))
    else:
        entitlement.active = True
    await session.commit()

    if trigger_sync:
        Celery(broker=get_settings().redis_url).send_task(
            "pomogator.sync_country", args=[country.slug]
        )
    return {"status": "succeeded", "provider": "stub"}


async def user_has_country_access(
    session: AsyncSession, *, user_id: UUID, country_id: UUID
) -> bool:
    return (
        await session.scalar(
            select(EntitlementModel.id).where(
                EntitlementModel.user_id == user_id,
                EntitlementModel.country_id == country_id,
                EntitlementModel.active,
            )
        )
        is not None
    )
