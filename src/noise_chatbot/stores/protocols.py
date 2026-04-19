"""Protocol classes for noise-chatbot's four pluggable stores.

<trl>
MODULE protocols CONTAINS PROCESS GuardrailStore AND PROCESS ResponseStore
    AND PROCESS BannedKeyStore AND PROCESS KnowledgeBaseStore.
EACH PROCESS 'is a INTERFACE contract WITH NO implementation.
</trl>

These are structural types (``typing.Protocol``) — any class that satisfies
the method signatures is an implementation, no inheritance required.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from noise_chatbot.server.server import ResponseNode


# AGENT guardrailstore SHALL DEFINE PROCESS.
@runtime_checkable
class GuardrailStore(Protocol):
    """Read-only access to the guardrail response nodes.

    <trl>
    PROCESS GuardrailStore SHALL RETURNS_TO SOURCE ARRAY guardrail_nodes.
    </trl>

    Typical implementations:
    - ``InMemoryGuardrailStore`` — compiled-in default (15 nodes) plus any
      callers appended via ``Server.with_guardrails(path)``
    - ``TrugsGuardrailStore`` — reads from a ``trugs_store`` graph
    """

    # FUNCTION guardrails SHALL RETURNS_TO SOURCE.
    def guardrails(self) -> list[ResponseNode]:
        """Return the current list of guardrail nodes (snapshot)."""
        ...


# AGENT responsestore SHALL DEFINE PROCESS.
@runtime_checkable
class ResponseStore(Protocol):
    """Read-only access to the response-node list used by classifiers.

    <trl>
    PROCESS ResponseStore SHALL RETURNS_TO SOURCE ARRAY response_nodes.
    </trl>
    """

    # FUNCTION responses SHALL RETURNS_TO SOURCE.
    def responses(self) -> list[ResponseNode]:
        """Return the current list of response nodes (snapshot)."""
        ...


# AGENT bannedkeystore SHALL DEFINE PROCESS.
@runtime_checkable
class BannedKeyStore(Protocol):
    """Read/write store for banned keys with a mandatory TTL.

    <trl>
    PROCESS BannedKeyStore SHALL WRITE RECORD ban THEN EXPIRE RECORD ban.
    EACH RECORD ban SHALL EXPIRE SUBJECT_TO RECORD ttl.
    </trl>

    **Threat model (locked 2026-04-19)**: bans are a SLOWDOWN mechanism,
    not PREVENTION. Every implementation **MUST** enforce ``ttl`` expiry —
    no permanent bans. ``is_banned`` must return ``False`` for keys whose
    ban timestamp is older than ``ttl`` from ``now``.

    The Go parity ban duration is 72 hours (triggered at 40 questions or
    honeypot tier 5).
    """

    ttl: timedelta

    # FUNCTION ban SHALL WRITE RECORD.
    def ban(self, key_hex: str, when: datetime | None = None) -> None:
        """Record a ban for ``key_hex`` at ``when`` (default: ``datetime.now()``)."""
        ...

    # FUNCTION is_banned SHALL VALIDATE RECORD.
    def is_banned(self, key_hex: str, *, now: datetime | None = None) -> bool:
        """Return ``True`` iff ``key_hex`` has an un-expired ban at ``now``."""
        ...

    # FUNCTION unban SHALL REVOKE RECORD.
    def unban(self, key_hex: str) -> None:
        """Remove ``key_hex`` from the store. No-op if absent."""
        ...

    # FUNCTION active_bans SHALL RETURNS_TO SOURCE.
    def active_bans(self, *, now: datetime | None = None) -> Iterable[tuple[str, datetime]]:
        """Return an eager snapshot of ``(key_hex, banned_at)`` for un-expired bans.

        Eager (not lazy) to avoid ``ban``/``unban``-during-iteration races.
        """
        ...


# AGENT knowledgebasestore SHALL DEFINE PROCESS.
@runtime_checkable
class KnowledgeBaseStore(Protocol):
    """Read-only access to the TRUG knowledge-base payload used for context injection.

    <trl>
    PROCESS KnowledgeBaseStore SHALL RETURNS_TO SOURCE RECORD trug_payload.
    </trl>

    Returns ``None`` when no knowledge base is loaded (default for a fresh
    ``Server`` without ``with_trug()`` or ``with_knowledge_base()``).
    """

    # FUNCTION context SHALL RETURNS_TO SOURCE.
    def context(self) -> dict[str, object] | None:
        """Return the raw TRUG dict, or ``None`` if not loaded."""
        ...
