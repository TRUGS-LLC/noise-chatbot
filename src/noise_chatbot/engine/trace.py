"""Trace log — every fork the walk visited, and every selection attempt made.

<trl>
ASSERT PROCESS engine SHALL WRITE RECORD trace TO FILE log.
INVARIANT PROCESS engine SHALL REQUIRE RECORD schema_version FROM EACH RECORD trace.
</trl>

The trace is the replay ledger: feeding its recorded attempt sequence back through the
same corpus reproduces the byte-identical answer + address (T2.5 replay determinism).
It carries ``trace_schema_version`` from day one (C3) so later consumers can migrate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

#: Bumped when the trace record shape changes (C3 — versioned from day one).
#: v2 (AAA #69 SP-B): the trace becomes a self-contained, third-party-checkable record —
#: it now carries the corpus_digest it is bound to (B1), the session grant-set that gated
#: its menus (B5), and the terminal delivered leaf (B4). All three are opt-in with defaults,
#: so a digest-less v1 TraceLog constructs byte-identically (B9).
TRACE_SCHEMA_VERSION: Final = "2"


@dataclass(frozen=True, slots=True)
class TraceAttempt:
    """One selection attempt at a fork: what the backend returned, and whether it was legal."""

    choice: str
    legal: bool


@dataclass(frozen=True, slots=True)
class TraceStep:
    """One visited fork: the cursor, the menu it presented, and the attempts made there."""

    cursor_id: str
    menu_ids: tuple[str, ...]
    attempts: tuple[TraceAttempt, ...]


@dataclass(frozen=True, slots=True)
class TraceTerminal:
    """The delivered leaf of a walk: where it actually ended (B4).

    Recording it copies an *id*, never authored text — the authored-leaf invariant is
    untouched. ``verify_trace`` binds this to the endpoint the legal walk reaches so the
    *delivered* answer is bound to the verified walk, not merely self-reported (RT-2).
    """

    leaf_id: str
    is_bottom: bool


@dataclass(slots=True)
class TraceLog:
    """An append-only record of a single walk.

    <trl>
    DEFINE RECORD trace CONTAINS RECORD schema_version AND ARRAY step AND RECORD corpus_digest AND RECORD grants AND RECORD terminal.
    </trl>
    """

    corpus_schema_version: str
    trace_schema_version: str = TRACE_SCHEMA_VERSION
    steps: list[TraceStep] = field(default_factory=list)
    #: The tci1-sha256 corpus_digest (SP-A) this walk is bound to — "" for a digest-less
    #: (v1 / opt-out) trace, which verify_trace still checks for legality but reports unbound.
    corpus_digest: str = ""
    #: The session grant-set that gated every menu (B5), sorted for a stable record — so the
    #: session-gated menu is independently re-derivable. Empty tuple for an anonymous session.
    grants: tuple[str, ...] = ()
    #: The terminal delivered leaf (B4) — set once at delivery; None for an in-flight/legacy trace.
    terminal: TraceTerminal | None = None

    def visit(
        self, cursor_id: str, menu_ids: tuple[str, ...], attempts: tuple[TraceAttempt, ...]
    ) -> None:
        """Record a visited fork and the selection attempts made there."""
        self.steps.append(TraceStep(cursor_id=cursor_id, menu_ids=menu_ids, attempts=attempts))

    def terminate(self, leaf_id: str, *, is_bottom: bool) -> None:
        """Record the delivered terminal leaf — called once, at delivery (B4)."""
        self.terminal = TraceTerminal(leaf_id=leaf_id, is_bottom=is_bottom)

    def replay_choices(self) -> list[str]:
        """Return every attempt's choice in order — the exact sequence to replay a walk.

        Includes off-menu attempts, so replaying reproduces retries and ⊥ routing
        identically (T2.5).
        """
        return [attempt.choice for step in self.steps for attempt in step.attempts]
