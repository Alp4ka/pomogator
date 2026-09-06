from pomogator.domain.content import AccessLevel, parse_access_title
from pomogator.domain.fields import annotate_document_fields, field_key, parse_checkbox_default


def test_access_pay_tag():
    assert parse_access_title("Виза {pmg.access.pay}") == ("Виза", AccessLevel.PAID)


def test_access_free_overrides_inherited():
    assert parse_access_title("Старт {pmg.access.free}", AccessLevel.PAID) == (
        "Старт",
        AccessLevel.FREE,
    )


def test_access_inherits_when_no_tag():
    assert parse_access_title("Документы", AccessLevel.PAID) == ("Документы", AccessLevel.PAID)


def test_checkbox_default_parsing():
    assert parse_checkbox_default("") is False
    assert parse_checkbox_default("false") is False
    assert parse_checkbox_default("true") is True
    assert parse_checkbox_default("да") is True


def test_annotate_input_and_checkbox_keys_stable():
    document = [
        {
            "type": "paragraph",
            "rich_text": [
                {
                    "text": "Имя {pmg.field.input({12,Ваше имя})} и {pmg.field.cb(false)} готово",
                    "annotations": {},
                }
            ],
        },
        {
            "type": "paragraph",
            "rich_text": [
                {
                    "text": "Снова {pmg.field.input({12,Ваше имя})}",
                    "annotations": {},
                }
            ],
        },
    ]
    annotated, specs = annotate_document_fields(document)
    assert len(specs) == 3
    first_input = next(r for r in annotated[0]["runs"] if r["type"] == "input")
    second_input = next(r for r in annotated[1]["runs"] if r["type"] == "input")
    assert first_input["key"] == field_key("input", "12\0ваше имя", 1)
    assert second_input["key"] == field_key("input", "12\0ваше имя", 2)
    assert first_input["key"] != second_input["key"]
    assert first_input["width"] == 12
    assert first_input["placeholder"] == "Ваше имя"
    cb = next(r for r in annotated[0]["runs"] if r["type"] == "checkbox")
    assert cb["default"] == "false"
    # Tags stripped from rich_text for PDF / plain consumers
    plain = "".join(part["text"] for part in annotated[0]["rich_text"])
    assert "{pmg." not in plain
