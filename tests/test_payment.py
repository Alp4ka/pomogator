from uuid import uuid4

from pomogator.domain.payments import StubPaymentProvider


async def test_stub_payment_is_deterministic():
    provider = StubPaymentProvider()
    first = await provider.purchase(uuid4(), uuid4(), "same-key")
    second = await provider.purchase(uuid4(), uuid4(), "same-key")
    assert first.succeeded is True
    assert first.external_id == second.external_id == "stub:same-key"
