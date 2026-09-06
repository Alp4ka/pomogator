from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from pomogator.application.content_sync import _is_active_run, sync_status_payload


def test_active_run_window():
    now = datetime.now(UTC)
    fresh = SimpleNamespace(status="running", started_at=now - timedelta(minutes=5))
    stale = SimpleNamespace(status="running", started_at=now - timedelta(minutes=45))
    done = SimpleNamespace(status="succeeded", started_at=now - timedelta(minutes=1))
    assert _is_active_run(fresh, now=now) is True
    assert _is_active_run(stale, now=now) is False
    assert _is_active_run(done, now=now) is False


def test_sync_status_payload_idle():
    country = SimpleNamespace(slug="brazil", content_version=3)
    payload = sync_status_payload(country, None)  # type: ignore[arg-type]
    assert payload["status"] == "idle"
    assert payload["content_version"] == 3
    assert payload["slug"] == "brazil"


def test_sync_status_payload_failed():
    country = SimpleNamespace(slug="brazil", content_version=4)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    run = SimpleNamespace(
        status="failed",
        error="notion 503",
        started_at=started,
        finished_at=started + timedelta(seconds=10),
        id=uuid4(),
    )
    payload = sync_status_payload(country, run)  # type: ignore[arg-type]
    assert payload["status"] == "failed"
    assert payload["error"] == "notion 503"
    assert payload["started_at"] is not None
