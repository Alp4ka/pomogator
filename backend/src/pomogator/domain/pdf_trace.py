"""Opaque PDF forensic stamps (seal/unseal user attribution).

The public stamp looks like a normal document UUID / cache token.
Payload is encrypted+authenticated — base64 alone does not reveal ids.
Offline decode needs the server secret; online decode can also use pdf_exports.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any
from uuid import UUID, uuid4

_NONCE_LEN = 16
_MAC_LEN = 16


def derive_trace_secret(raw: str) -> bytes:
    material = raw.encode("utf-8") if raw else b"pomogator-dev-pdf-trace"
    return hashlib.sha256(b"pomogator:pdf-trace:v1:" + material).digest()


def _keystream(secret: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(
            secret,
            b"pomogator:pdf-trace:stream:v1:" + nonce + counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def seal_trace(secret: bytes, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    nonce = os.urandom(_NONCE_LEN)
    stream = _keystream(secret, nonce, len(body))
    ciphertext = bytes(a ^ b for a, b in zip(body, stream, strict=True))
    digest = hmac.new(
        secret,
        b"pomogator:pdf-trace:mac:v1:" + nonce + ciphertext,
        hashlib.sha256,
    ).digest()[:_MAC_LEN]
    return base64.urlsafe_b64encode(nonce + digest + ciphertext).decode("ascii").rstrip("=")


def unseal_trace(secret: bytes, token: str) -> dict[str, Any]:
    padded = token + ("=" * (-len(token) % 4))
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    if len(raw) < _NONCE_LEN + _MAC_LEN + 1:
        raise ValueError("trace token too short")
    nonce = raw[:_NONCE_LEN]
    digest = raw[_NONCE_LEN : _NONCE_LEN + _MAC_LEN]
    ciphertext = raw[_NONCE_LEN + _MAC_LEN :]
    expected = hmac.new(
        secret,
        b"pomogator:pdf-trace:mac:v1:" + nonce + ciphertext,
        hashlib.sha256,
    ).digest()[:_MAC_LEN]
    if not hmac.compare_digest(digest, expected):
        raise ValueError("trace token signature mismatch")
    body = bytes(
        a ^ b for a, b in zip(ciphertext, _keystream(secret, nonce, len(ciphertext)), strict=True)
    )
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trace token payload must be an object")
    return data


def new_export_id() -> UUID:
    return uuid4()


def disguise_token(token: str) -> str:
    """Make the sealed blob look like a build/cache identifier in metadata."""
    return f"build/{token[:8]}/{token[8:]}"


def extract_disguised_token(value: str) -> str | None:
    if value.startswith("build/") and value.count("/") >= 2:
        _, prefix, rest = value.split("/", 2)
        if len(prefix) == 8 and rest:
            return prefix + rest
    return None
