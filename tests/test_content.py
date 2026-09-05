from pomogator.domain.content import AccessLevel, parse_access_title


def test_paid_tag_is_removed():
    assert parse_access_title("Виза [Платным]") == ("Виза", AccessLevel.PAID)


def test_access_is_inherited_without_tag():
    assert parse_access_title("Документы", AccessLevel.PAID) == ("Документы", AccessLevel.PAID)


def test_free_override():
    assert parse_access_title("[Бесплатно] Старт", AccessLevel.PAID) == ("Старт", AccessLevel.FREE)
