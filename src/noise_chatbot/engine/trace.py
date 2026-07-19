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
TRACE_SCHEMA_VERSION: Final = "1"


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


@dataclass(slots=True)
class TraceLog:
    """An append-only record of a single walk.

    <trl>
    DEFINE RECORD trace CONTAINS RECORD schema_version AND ARRAY step.
    </trl>
    """

    corpus_schema_version: str
    trace_schema_version: str = TRACE_SCHEMA_VERSION
    steps: list[TraceStep] = field(default_factory=list)

    def visit(
        self, cursor_id: str, menu_ids: tuple[str, ...], attempts: tuple[TraceAttempt, ...]
    ) -> None:
        """Record a visited fork and the selection attempts made there."""
        self.steps.append(TraceStep(cursor_id=cursor_id, menu_ids=menu_ids, attempts=attempts))

    def replay_choices(self) -> list[str]:
        """Return every attempt's choice in order — the exact sequence to replay a walk.

        Includes off-menu attempts, so replaying reproduces retries and ⊥ routing
        identically (T2.5).
        """
        return [attempt.choice for step in self.steps for attempt in step.attempts]
