import io
from uuid import uuid4

from PIL import Image
from pomogator.domain.pdf_trace import (
    derive_trace_secret,
    disguise_token,
    extract_disguised_token,
    seal_trace,
    unseal_trace,
)
from pomogator.infrastructure.pdf.render import (
    _cell_text,
    _color_emoji_image,
    _plain,
    _register_fonts,
    _wrap,
    render_page_pdf,
    split_callout_text,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


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


def test_register_fonts_uses_bundled_unicode_face():
    _register_fonts.cache_clear()
    regular, bold, extras = _register_fonts()
    assert regular == "GuideSans"
    assert bold == "GuideSans-Bold"
    assert "GuideEmoji" in extras
    assert "GuideSymbols" in extras


def test_split_callout_keeps_bold_title_and_body():
    assert split_callout_text(
        [
            {"text": "Кондиционер в квартире ОБЯЗАТЕЛЕН", "annotations": {"bold": True}},
            {"text": " В жаркие месяцы без него спать почти невозможно."},
        ]
    ) == (
        "Кондиционер в квартире ОБЯЗАТЕЛЕН",
        "В жаркие месяцы без него спать почти невозможно.",
    )


def test_wrap_keeps_russian_paragraph_on_few_lines():
    _register_fonts.cache_clear()
    regular, _bold, extras = _register_fonts()
    pdf = canvas.Canvas(io.BytesIO(), pagesize=A4)
    text = (
        "В жаркие месяцы без него спать почти невозможно, особенно с маленьким "
        "ребёнком. Ищите объявления с split-системой и уточняйте, входит ли электричество в аренду."
    )
    lines = _wrap(pdf, text, regular, 11, 460, extras)
    assert 2 <= len(lines) <= 4
    assert all(" " in line or len(line) > 12 for line in lines)


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
    assert b"DejaVu" in pdf


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


def test_plain_uses_field_state_for_inputs_and_checkboxes():
    runs = [
        {"type": "text", "text": "A "},
        {"type": "input", "key": "name", "width": 10, "placeholder": "ФИО"},
        {"type": "text", "text": " "},
        {"type": "checkbox", "key": "done", "default": "false"},
    ]
    assert _plain(runs, {"name": "Иван", "done": "true"}) == "A Иван ☑"
    assert _plain(runs, {}) == "A [ФИО] ☐"


def test_render_pdf_prefers_runs_and_field_values():
    export_id = uuid4()
    pdf = render_page_pdf(
        title="Гид",
        document=[
            {
                "type": "paragraph",
                "rich_text": [{"text": "hidden"}],
                "runs": [
                    {"type": "text", "text": "Статус: "},
                    {"type": "checkbox", "key": "ok", "default": "false"},
                    {"type": "text", "text": " / "},
                    {"type": "input", "key": "note", "width": 8, "placeholder": "x"},
                ],
            }
        ],
        export_id=export_id,
        sealed_token="token",
        field_values={"ok": "true", "note": "готово"},
    )
    assert pdf.startswith(b"%PDF")
    assert b"hidden" not in pdf
    assert b"DejaVu" in pdf


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
    assert b"DejaVu" in pdf


def test_color_emoji_uses_bundled_noto_color_glyphs():
    house = _color_emoji_image("🏠")
    flag = _color_emoji_image("🇧🇷")
    assert house is not None
    assert flag is not None
    assert house[1] >= 32 and house[2] >= 32
    assert flag[1] >= 32 and flag[2] >= 32
    assert _color_emoji_image("Ж") is None
    assert _color_emoji_image("☐") is None
    image = Image.open(io.BytesIO(flag[0])).convert("RGBA")
    greens = 0
    for x in range(0, image.width, 3):
        for y in range(0, image.height, 3):
            pixel = image.getpixel((x, y))
            if (
                isinstance(pixel, tuple)
                and len(pixel) == 4
                and pixel[3] > 200
                and pixel[1] > pixel[0] + 25
                and pixel[1] > pixel[2] + 25
            ):
                greens += 1
    assert greens > 10, "Brazil flag must keep the green field, not ISO letter pills"


def test_render_pdf_keeps_emoji_and_document_blocks():
    export_id = uuid4()
    pdf = render_page_pdf(
        title="Жуан-Песоа 🇧🇷",
        document=[
            {"type": "heading_2", "rich_text": [{"text": "Почему выбирают Жуан"}]},
            {
                "type": "callout",
                "icon": "🏠",
                "rich_text": [
                    {"text": "качество жизни", "annotations": {"bold": True}},
                    {"text": " спокойный безопасный город"},
                ],
            },
            {
                "type": "quote",
                "rich_text": [{"text": "Не откладывайте страховку на первую неделю."}],
            },
            {"type": "bulleted_list_item", "rich_text": [{"text": "Качественная медицина"}]},
        ],
        export_id=export_id,
        sealed_token="token",
    )
    assert pdf.startswith(b"%PDF")
    assert b"DejaVu" in pdf
    assert b"/Image" in pdf
    assert _color_emoji_image("🏠") is not None
    assert _color_emoji_image("🇧🇷") is not None
    assert _color_emoji_image("Ж") is None
