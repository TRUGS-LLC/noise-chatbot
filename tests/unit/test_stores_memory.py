"""Concrete conformance tests for the ``InMemory*`` default stores.

<trl>
STAGE test_stores_memory SHALL VALIDATE RECORD InMemoryGuardrailStore
    AND RECORD InMemoryResponseStore AND RECORD InMemoryBannedKeyStore
    AND RECORD InMemoryKnowledgeBaseStore.
</trl>
"""

from __future__ import annotations

from datetime import datetime, timedelta

from noise_chatbot.stores import (
    BannedKeyStore,
    GuardrailStore,
    InMemoryBannedKeyStore,
    InMemoryGuardrailStore,
    InMemoryKnowledgeBaseStore,
    InMemoryResponseStore,
    KnowledgeBaseStore,
    ResponseStore,
)
from tests.unit._store_suite import (
    BannedKeyStoreSuite,
    GuardrailStoreSuite,
    KnowledgeBaseStoreSuite,
    ResponseStoreSuite,
    _FakeResponseNode,
)


# AGENT SHALL VALIDATE PROCESS inmemoryguardrailstore.
class TestInMemoryGuardrailStore(GuardrailStoreSuite):
    store_factory = staticmethod(InMemoryGuardrailStore)

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        """Runtime-checkable Protocol isinstance check."""
        assert isinstance(InMemoryGuardrailStore(), GuardrailStore)

    # AGENT SHALL VALIDATE PROCESS init_with_nodes.
    def test_init_with_nodes(self) -> None:
        nodes: list[_FakeResponseNode] = [_FakeResponseNode(id="a", keywords=["x"], response="A")]
        store = InMemoryGuardrailStore(nodes)  # type: ignore[arg-type]
        assert len(store.guardrails()) == 1
        assert store.guardrails()[0].id == "a"

    # AGENT SHALL VALIDATE PROCESS extend_appends.
    def test_extend_appends(self) -> None:
        store = InMemoryGuardrailStore()
        store.extend([_FakeResponseNode(id="a", keywords=[], response="A")])  # type: ignore[list-item]
        store.extend([_FakeResponseNode(id="b", keywords=[], response="B")])  # type: ignore[list-item]
        ids = [n.id for n in store.guardrails()]
        assert ids == ["a", "b"]


# AGENT SHALL VALIDATE PROCESS inmemoryresponsestore.
class TestInMemoryResponseStore(ResponseStoreSuite):
    store_factory = staticmethod(InMemoryResponseStore)

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(InMemoryResponseStore(), ResponseStore)

    # AGENT SHALL VALIDATE PROCESS init_with_nodes.
    def test_init_with_nodes(self) -> None:
        nodes: list[_FakeResponseNode] = [
            _FakeResponseNode(id="pricing", keywords=["price"], response="$10")
        ]
        store = InMemoryResponseStore(nodes)  # type: ignore[arg-type]
        assert store.responses()[0].id == "pricing"


# AGENT SHALL VALIDATE PROCESS inmemorybannedkeystore.
class TestInMemoryBannedKeyStore(BannedKeyStoreSuite):
    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    @staticmethod
    def store_factory() -> InMemoryBannedKeyStore:
        # Short-ish TTL — expiry tests drive `now` explicitly so wall clock doesn't matter.
        return InMemoryBannedKeyStore(ttl=timedelta(hours=1))

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(InMemoryBannedKeyStore(), BannedKeyStore)

    # AGENT SHALL VALIDATE PROCESS default_ttl_72h.
    def test_default_ttl_72h(self) -> None:
        """Zero-arg constructor uses the 72h Go parity default."""
        assert InMemoryBannedKeyStore().ttl == timedelta(hours=72)

    # AGENT SHALL VALIDATE PROCESS expired_ban_cleaned_eagerly.
    def test_expired_ban_cleaned_eagerly(self) -> None:
        """Calling ``is_banned`` on an expired entry removes it from the internal map."""
        store = InMemoryBannedKeyStore(ttl=timedelta(hours=1))
        base = datetime(2026, 1, 1, 12, 0, 0)
        store.ban("abc", when=base)
        # Expire + check
        assert store.is_banned("abc", now=base + timedelta(hours=2)) is False
        # Active list also reports empty
        assert list(store.active_bans(now=base + timedelta(hours=2))) == []


# AGENT SHALL VALIDATE PROCESS inmemoryknowledgebasestore.
class TestInMemoryKnowledgeBaseStore(KnowledgeBaseStoreSuite):
    store_factory = staticmethod(InMemoryKnowledgeBaseStore)

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(InMemoryKnowledgeBaseStore(), KnowledgeBaseStore)

    # AGENT SHALL VALIDATE PROCESS init_with_data.
    def test_init_with_data(self) -> None:
        payload: dict[str, object] = {"name": "KB", "nodes": []}
        store = InMemoryKnowledgeBaseStore(payload)
        assert store.context() == payload
