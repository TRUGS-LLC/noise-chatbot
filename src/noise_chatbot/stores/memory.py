"""In-memory default implementations for the four stores (zero external deps).

<trl>
MODULE memory CONTAINS RECORD InMemoryGuardrailStore AND RECORD InMemoryResponseStore
    AND RECORD InMemoryBannedKeyStore AND RECORD InMemoryKnowledgeBaseStore.
EACH RECORD IMPLEMENTS PROCESS store.
</trl>
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_chatbot.server.server import ResponseNode


# AGENT inmemoryguardrailstore SHALL IMPLEMENT PROCESS.
class InMemoryGuardrailStore:
    """Holds guardrail nodes as a plain list in process memory.

    <trl>
    RECORD InMemoryGuardrailStore CONTAINS ARRAY nodes.
    </trl>
    """

    __slots__ = ("_nodes",)

    def __init__(self, nodes: list[ResponseNode] | None = None) -> None:
        self._nodes: list[ResponseNode] = list(nodes) if nodes is not None else []

    # FUNCTION guardrails SHALL RETURNS_TO SOURCE.
    def guardrails(self) -> list[ResponseNode]:
        return list(self._nodes)

    # FUNCTION extend SHALL WRITE DATA.
    def extend(self, nodes: Iterable[ResponseNode]) -> None:
        """Append ``nodes`` to the current list (used by ``with_guardrails(path)``)."""
        self._nodes.extend(nodes)


# AGENT inmemoryresponsestore SHALL IMPLEMENT PROCESS.
class InMemoryResponseStore:
    """Holds response nodes as a plain list in process memory.

    <trl>
    RECORD InMemoryResponseStore CONTAINS ARRAY nodes.
    </trl>
    """

    __slots__ = ("_nodes",)

    def __init__(self, nodes: list[ResponseNode] | None = None) -> None:
        self._nodes: list[ResponseNode] = list(nodes) if nodes is not None else []

    # FUNCTION responses SHALL RETURNS_TO SOURCE.
    def responses(self) -> list[ResponseNode]:
        return list(self._nodes)


# AGENT inmemorybannedkeystore SHALL IMPLEMENT PROCESS.
class InMemoryBannedKeyStore:
    """Thread-safe in-process ban store with TTL-enforced expiry.

    <trl>
    RECORD InMemoryBannedKeyStore CONTAINS OBJECT bans AND RECORD ttl.
    FUNCTION is_banned SHALL VALIDATE RECORD ban SUBJECT_TO RECORD ttl.
    </trl>

    Go-parity default: 72-hour TTL.
    """

    __slots__ = ("_bans", "_lock", "ttl")

    def __init__(self, ttl: timedelta = timedelta(hours=72)) -> None:
        self.ttl: timedelta = ttl
        self._bans: dict[str, datetime] = {}
        self._lock = threading.Lock()

    # FUNCTION ban SHALL WRITE RECORD.
    def ban(self, key_hex: str, when: datetime | None = None) -> None:
        ts = when if when is not None else datetime.now()
        with self._lock:
            self._bans[key_hex] = ts

    # FUNCTION is_banned SHALL VALIDATE RECORD.
    def is_banned(self, key_hex: str, *, now: datetime | None = None) -> bool:
        current = now if now is not None else datetime.now()
        with self._lock:
            banned_at = self._bans.get(key_hex)
            if banned_at is None:
                return False
            if current - banned_at >= self.ttl:
                # Eager cleanup on read.
                self._bans.pop(key_hex, None)
                return False
            return True

    # FUNCTION unban SHALL REVOKE RECORD.
    def unban(self, key_hex: str) -> None:
        with self._lock:
            self._bans.pop(key_hex, None)

    # FUNCTION active_bans SHALL RETURNS_TO SOURCE.
    def active_bans(self, *, now: datetime | None = None) -> Iterable[tuple[str, datetime]]:
        current = now if now is not None else datetime.now()
        with self._lock:
            return [(k, ts) for k, ts in self._bans.items() if current - ts < self.ttl]


# AGENT inmemoryknowledgebasestore SHALL IMPLEMENT PROCESS.
class InMemoryKnowledgeBaseStore:
    """Holds a TRUG dict in process memory.

    <trl>
    RECORD InMemoryKnowledgeBaseStore CONTAINS OBJECT trug_data.
    </trl>
    """

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, object] | None = None) -> None:
        self._data: dict[str, object] | None = data

    # FUNCTION context SHALL RETURNS_TO SOURCE.
    def context(self) -> dict[str, object] | None:
        return self._data
