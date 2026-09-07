from uuid import uuid4

from pomogator.domain.content import (
    AccessLevel,
    normalize_nav_label,
    parse_access_title,
    parse_page_title,
)
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


def test_page_title_extracts_nav_label():
    title, level, label = parse_page_title(
        "Этап 1 {pmg.nav.page(cpf)} {pmg.access.pay}", AccessLevel.FREE
    )
    assert title == "Этап 1"
    assert level == AccessLevel.PAID
    assert label == "cpf"


def test_normalize_nav_label_rejects_empty_and_junk():
    assert normalize_nav_label("  ok_label-1.2 ") == "ok_label-1.2"
    assert normalize_nav_label("") is None
    assert normalize_nav_label("bad label") is None


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


def test_annotate_nav_goto_and_gotopage():
    target = uuid4()
    document = [
        {
            "type": "heading_2",
            "rich_text": [{"text": "Раздел {pmg.nav.label(docs)}", "annotations": {}}],
        },
        {
            "type": "paragraph",
            "rich_text": [
                {
                    "text": (
                        "См. {pmg.nav.goto(docs, чек-лист)} и "
                        "{pmg.nav.gotopage(cpf, CPF)} плюс "
                        "{pmg.field.cb(true)}"
                    ),
                    "annotations": {"bold": True},
                }
            ],
        },
        {
            "type": "paragraph",
            "rich_text": [
                {"text": "Битый {pmg.nav.goto(missing, якорь)} и {pmg.nav.gotopage(nope, стр)}"}
            ],
        },
    ]
    annotated, specs = annotate_document_fields(document, page_nav={"cpf": target})
    assert annotated[0]["nav_anchor"] == "docs"
    assert all(run.get("type") != "nav_label" for run in annotated[0]["runs"])
    goto = next(
        run
        for run in annotated[1]["runs"]
        if run.get("type") == "text" and run.get("text") == "чек-лист"
    )
    assert goto["link"] == {"type": "anchor", "label": "docs"}
    assert goto["annotations"]["bold"] is True
    gotopage = next(
        run
        for run in annotated[1]["runs"]
        if run.get("type") == "text" and run.get("text") == "CPF"
    )
    assert gotopage["link"] == {"type": "internal", "page_id": str(target)}
    assert len(specs) == 1
    plain = "".join(part["text"] for part in annotated[2]["rich_text"])
    assert plain == "Битый якорь и стр"
    assert all("link" not in part for part in annotated[2]["rich_text"])
    assert "{pmg." not in "".join(part["text"] for part in annotated[1]["rich_text"])
