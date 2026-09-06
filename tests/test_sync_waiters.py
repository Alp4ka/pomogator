from pomogator.application.sync_waiters import pop_sync_waiters, register_sync_waiter


def test_sync_waiter_roundtrip(monkeypatch):
    store: dict[str, set[str]] = {}

    class FakeRedis:
        def sadd(self, key: str, value: str) -> int:
            store.setdefault(key, set()).add(value)
            return 1

        def expire(self, key: str, ttl: int) -> bool:
            return True

        def smembers(self, key: str) -> set[str]:
            return set(store.get(key, set()))

        def delete(self, key: str) -> int:
            return 1 if store.pop(key, None) is not None else 0

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "pomogator.application.sync_waiters._client",
        lambda: FakeRedis(),
    )
    register_sync_waiter("brazil", 111)
    register_sync_waiter("brazil", 222)
    register_sync_waiter("brazil", 111)
    assert pop_sync_waiters("brazil") == [111, 222]
    assert pop_sync_waiters("brazil") == []
