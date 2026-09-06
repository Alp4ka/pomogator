from pomogator.domain.sync_errors import (
    NotionSyncError,
    USER_SYNC_FAILED,
    USER_SYNC_RATE_LIMITED,
    user_facing_sync_error,
)


def test_user_facing_hides_notion_urls():
    raw = (
        "Client error '429 Too Many Requests' for url "
        "'https://api.notion.com/v1/blocks/3b745344-c787-8099-a063-cea0ee14abec/children'"
    )
    message = user_facing_sync_error(RuntimeError(raw))
    assert "api.notion.com" not in message
    assert "http" not in message.casefold()
    assert message == USER_SYNC_RATE_LIMITED


def test_user_facing_notion_sync_error_code():
    assert user_facing_sync_error(NotionSyncError("unavailable")) != USER_SYNC_RATE_LIMITED
    assert "http" not in user_facing_sync_error(NotionSyncError("failed")).casefold()
    assert user_facing_sync_error(Exception("boom")) == USER_SYNC_FAILED
