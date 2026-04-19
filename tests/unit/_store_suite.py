"""Abstract conformance `TestSuite` classes for the four store Protocols.

<trl>
MODULE _store_suite CONTAINS RECORD GuardrailStoreSuite AND RECORD ResponseStoreSuite
    AND RECORD BannedKeyStoreSuite AND RECORD KnowledgeBaseStoreSuite.
EACH RECORD SHALL VALIDATE PROCESS store.
</trl>

Every concrete store implementation should subclass the relevant suite and
provide a ``store_factory`` classmethod/staticmethod. The suite's tests then
run against the factory's output. This ensures every implementation
(InMemory, JsonFile, Trugs) satisfies the same observable contract.

Naming: suite classes start with ``Suite`` (not ``Test``) so pytest does NOT
collect them directly — only via concrete subclasses.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class _FakeResponseNode:
    """Minimal ResponseNode-shaped object for tests (duck-typed)."""

    id: str
    keywords: list[str]
    response: str


# Store factory type alias — subclasses provide any zero-arg callable
# (staticmethod, classmethod, or plain function) that builds a fresh store.
_StoreFactory = Callable[[], Any]


# AGENT guardrailstoresuite SHALL VALIDATE PROCESS.
class GuardrailStoreSuite:
    """Contract tests every `GuardrailStore` impl must pass.

    <trl>
    RECORD GuardrailStoreSuite SHALL VALIDATE PROCESS store.
    </trl>
    """

    store_factory: _StoreFactory  # override in subclass

    # AGENT SHALL VALIDATE PROCESS empty_store_returns_empty_list.
    def test_empty_store_returns_empty_list(self) -> None:
        """A store with no nodes returns an empty list."""
        store = self.store_factory()
        assert store.guardrails() == []

    # AGENT SHALL VALIDATE PROCESS guardrails_returns_snapshot.
    def test_guardrails_returns_snapshot(self) -> None:
        """``guardrails()`` returns a list — not a live reference to internals."""
        store = self.store_factory()
        r1 = store.guardrails()
        store.guardrails()  # second call for snapshot independence
        r1.append(_FakeResponseNode(id="x", keywords=[], response=""))
        assert store.guardrails() != r1


# AGENT responsestoresuite SHALL VALIDATE PROCESS.
class ResponseStoreSuite:
    """Contract tests every `ResponseStore` impl must pass.

    <trl>
    RECORD ResponseStoreSuite SHALL VALIDATE PROCESS store.
    </trl>
    """

    store_factory: _StoreFactory  # override in subclass

    # AGENT SHALL VALIDATE PROCESS empty_store_returns_empty_list.
    def test_empty_store_returns_empty_list(self) -> None:
        store = self.store_factory()
        assert store.responses() == []

    # AGENT SHALL VALIDATE PROCESS responses_returns_snapshot.
    def test_responses_returns_snapshot(self) -> None:
        store = self.store_factory()
        r = store.responses()
        r.append(_FakeResponseNode(id="x", keywords=[], response=""))
        assert store.responses() != r


# AGENT bannedkeystoresuite SHALL VALIDATE PROCESS.
class BannedKeyStoreSuite:
    """Contract tests every `BannedKeyStore` impl must pass.

    <trl>
    RECORD BannedKeyStoreSuite SHALL VALIDATE PROCESS store SUBJECT_TO RECORD ttl.
    </trl>
    """

    store_factory: _StoreFactory  # override in subclass

    # AGENT SHALL VALIDATE PROCESS fresh_store_reports_no_bans.
    def test_fresh_store_reports_no_bans(self) -> None:
        store = self.store_factory()
        assert store.is_banned("any-key") is False
        assert list(store.active_bans()) == []

    # AGENT SHALL VALIDATE PROCESS ban_then_is_banned.
    def test_ban_then_is_banned(self) -> None:
        store = self.store_factory()
        store.ban("abc123")
        assert store.is_banned("abc123") is True

    # AGENT SHALL VALIDATE PROCESS unban.
    def test_unban(self) -> None:
        store = self.store_factory()
        store.ban("abc123")
        store.unban("abc123")
        assert store.is_banned("abc123") is False

    # AGENT SHALL VALIDATE PROCESS unban_nonexistent_is_noop.
    def test_unban_nonexistent_is_noop(self) -> None:
        store = self.store_factory()
        # Should not raise
        store.unban("never-banned")

    # AGENT SHALL VALIDATE PROCESS ban_overwrites_timestamp.
    def test_ban_overwrites_timestamp(self) -> None:
        """Banning an already-banned key updates the timestamp."""
        store = self.store_factory()
        t1 = datetime(2026, 1, 1, 12, 0, 0)
        t2 = datetime(2026, 1, 2, 12, 0, 0)
        store.ban("abc123", when=t1)
        store.ban("abc123", when=t2)
        bans = dict(store.active_bans(now=t2))
        assert bans["abc123"] == t2

    # AGENT SHALL VALIDATE PROCESS ttl_expiry.
    def test_ttl_expiry(self) -> None:
        """A ban older than ``ttl`` reads as unbanned."""
        store = self.store_factory()
        ttl: timedelta = store.ttl
        banned_at = datetime(2026, 1, 1, 12, 0, 0)
        store.ban("abc123", when=banned_at)
        # just before expiry
        before = banned_at + ttl - timedelta(seconds=1)
        assert store.is_banned("abc123", now=before) is True
        # at / after expiry
        after = banned_at + ttl + timedelta(seconds=1)
        assert store.is_banned("abc123", now=after) is False

    # AGENT SHALL VALIDATE PROCESS active_bans_excludes_expired.
    def test_active_bans_excludes_expired(self) -> None:
        store = self.store_factory()
        ttl: timedelta = store.ttl
        base = datetime(2026, 1, 1, 12, 0, 0)
        store.ban("fresh", when=base)
        store.ban("stale", when=base - ttl - timedelta(hours=1))
        active = dict(store.active_bans(now=base))
        assert "fresh" in active
        assert "stale" not in active

    # AGENT SHALL VALIDATE PROCESS active_bans_is_eager_snapshot.
    def test_active_bans_is_eager_snapshot(self) -> None:
        """``active_bans`` is a list, not a lazy iterator — safe to mutate during iteration."""
        store = self.store_factory()
        store.ban("a")
        store.ban("b")
        # Force snapshot, then mutate.
        snapshot = list(store.active_bans())
        store.unban("a")
        store.unban("b")
        # Snapshot must still hold both.
        assert {k for k, _ in snapshot} == {"a", "b"}


# AGENT knowledgebasestoresuite SHALL VALIDATE PROCESS.
class KnowledgeBaseStoreSuite:
    """Contract tests every `KnowledgeBaseStore` impl must pass.

    <trl>
    RECORD KnowledgeBaseStoreSuite SHALL VALIDATE PROCESS store.
    </trl>
    """

    store_factory: _StoreFactory  # override in subclass

    # AGENT SHALL VALIDATE PROCESS empty_store_returns_none.
    def test_empty_store_returns_none(self) -> None:
        store = self.store_factory()
        assert store.context() is None
