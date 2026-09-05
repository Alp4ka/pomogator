from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaymentResult:
    external_id: str
    succeeded: bool


class PaymentProvider(Protocol):
    async def purchase(
        self, user_id: UUID, country_id: UUID, idempotency_key: str
    ) -> PaymentResult: ...


class StubPaymentProvider:
    async def purchase(
        self, user_id: UUID, country_id: UUID, idempotency_key: str
    ) -> PaymentResult:
        return PaymentResult(external_id=f"stub:{idempotency_key}", succeeded=True)
