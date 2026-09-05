from pomogator.infrastructure.notion.client import NotionClient


def test_extracts_notion_page_id():
    assert (
        NotionClient.notion_page_id("https://notion.so/Demo-3b345344c78780e9817cf27f963a1893")
        == "3b345344c78780e9817cf27f963a1893"
    )


def test_external_link_has_no_notion_id():
    assert NotionClient.notion_page_id("https://example.com/abc") is None


def test_rejects_notion_lookalike_host():
    assert (
        NotionClient.notion_page_id(
            "https://notion.so.evil.example/3b345344c78780e9817cf27f963a1893"
        )
        is None
    )


def test_external_url_allowlist():
    assert NotionClient.safe_external_url("https://example.com/path") == "https://example.com/path"
    assert NotionClient.safe_external_url("javascript:alert(1)") is None
    assert NotionClient.safe_external_url("http://example.com") is None
