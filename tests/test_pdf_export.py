from uuid import uuid4

from pomogator.domain.pdf_trace import (
    derive_trace_secret,
    disguise_token,
    extract_disguised_token,
    seal_trace,
    unseal_trace,
)
from pomogator.infrastructure.pdf.render import _cell_text, render_page_pdf


def test_seal_roundtrip_contains_user_and_subscription_fields():
    import base64

    secret = derive_trace_secret("unit-test-secret")
    uid = str(uuid4())
    payload = {
        "v": 1,
        "eid": str(uuid4()),
        "uid": uid,
        "tg": 123456789,
        "pid": str(uuid4()),
        "cid": str(uuid4()),
        "ent": True,
        "ts": 1_700_000_000,
    }
    token = seal_trace(secret, payload)
    # Ciphertext must not leak identifiers even after naive base64 decode.
    padded = token + ("=" * (-len(token) % 4))
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    assert b"123456789" not in raw
    assert uid.encode("ascii") not in raw
    assert unseal_trace(secret, token) == payload
    try:
        unseal_trace(derive_trace_secret("other-secret"), token)
        raise AssertionError("wrong secret must fail")
    except ValueError:
        pass
    disguised = disguise_token(token)
    assert disguised.startswith("build/")
    assert extract_disguised_token(disguised) == token


def test_render_pdf_embeds_disguised_trace():
    export_id = uuid4()
    secret = derive_trace_secret("unit-test-secret")
    sealed = seal_trace(
        secret,
        {
            "v": 1,
            "eid": str(export_id),
            "uid": str(uuid4()),
            "tg": 42,
            "pid": str(uuid4()),
            "cid": str(uuid4()),
            "ent": False,
            "ts": 1,
        },
    )
    pdf = render_page_pdf(
        title="Тест",
        document=[{"type": "paragraph", "rich_text": [{"text": "Привет"}]}],
        export_id=export_id,
        sealed_token=sealed,
    )
    assert pdf.startswith(b"%PDF")
    assert disguise_token(sealed).encode("ascii") in pdf
    assert str(export_id).encode("ascii") in pdf


def test_cell_text_from_annotated_dict():
    assert (
        _cell_text(
            {
                "rich_text": [{"text": "Получаете CPF"}],
                "runs": [{"type": "text", "text": "Получаете CPF"}],
            }
        )
        == "Получаете CPF"
    )
    assert _cell_text([{"text": "1"}]) == "1"


def test_render_pdf_table_cells_are_readable_text():
    export_id = uuid4()
    pdf = render_page_pdf(
        title="Гид",
        document=[
            {
                "type": "table",
                "rows": [
                    [
                        {
                            "rich_text": [{"text": "Этап"}],
                            "runs": [{"type": "text", "text": "Этап"}],
                        },
                        {
                            "rich_text": [{"text": "Что делаете"}],
                            "runs": [{"type": "text", "text": "Что делаете"}],
                        },
                    ],
                    [
                        [{"text": "1"}],
                        {
                            "rich_text": [{"text": "Получаете CPF"}],
                            "runs": [{"type": "text", "text": "Получаете CPF"}],
                        },
                    ],
                ],
            }
        ],
        export_id=export_id,
        sealed_token="token",
    )
    assert pdf.startswith(b"%PDF")
    # Annotated cell dicts must not be dumped into the PDF stream.
    assert b"rich_text" not in pdf
    assert b"annotations" not in pdf
    assert b"strikethrough" not in pdf
