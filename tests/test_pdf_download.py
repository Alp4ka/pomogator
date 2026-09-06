import base64
import json
from typing import Any

import pytest

from pomogator.application.pdf_download import pop_pdf_download, store_pdf_download


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


@pytest.mark.asyncio
async def test_pdf_download_roundtrip():
    redis: Any = FakeRedis()
    token = await store_pdf_download(redis, pdf_bytes=b"%PDF-1.4", filename="Виза.pdf")
    assert token
    stored = await pop_pdf_download(redis, token)
    assert stored == (b"%PDF-1.4", "Виза.pdf")
    assert await pop_pdf_download(redis, token) is None


@pytest.mark.asyncio
async def test_pdf_download_rejects_corrupt_payload():
    redis: Any = FakeRedis()
    token = "abc123tokenvalue"
    redis.values[f"pomogator:pdf-dl:{token}"] = json.dumps(
        {"filename": "x.pdf", "data": base64.b64encode(b"not-validated").decode("ascii") + "!"}
    )
    # Invalid base64 with validate=True
    assert await pop_pdf_download(redis, token) is None
