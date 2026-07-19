"""GapStore — located records of every ⊥ the engine hits (D8, the IP line).

<trl>
SERVICE gap_store SHALL WRITE EACH RECORD gap TO FILE ledger.
SERVICE gap_store SHALL REQUIRE RECORD ttl_config.
INVARIANT SERVICE gap_store SHALL REQUIRE RECORD schema_version.
</trl>

**Capture-never-compose.** A gap record indexes *where* the walk died (``death_node``)
and the raw query that missed — it is a located coverage signal for a human author, and
**nothing more**. This module imports no corpus and no LLM/selection code: there is no
path from a gap record back to answer authorship. Corpora mutate only via a human author
→ ``trug validate`` → a new version.

Raw-query retention is **TTL-bounded** (default 90 days, operator-configurable): expired
records are excluded from reads and dropped by ``prune`` (the D8 retention rider).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

#: Bumped when the gap record shape changes (C3 — versioned from day one).
GAP_SCHEMA_VERSION: Final = "1"

#: Default raw-query retention window (D8 retention rider, operator-configurable).
DEFAULT_TTL: Final = timedelta(days=90)

# ⊥ kinds — which bottom absorbed the miss (C4 discriminator).
KIND_ROOT_BOTTOM: Final = "root-⊥"
KIND_DEEP_BOTTOM: Final = "deep-⊥"


@dataclass(frozen=True, slots=True)
class GapRecord:
    """One located ⊥: where the walk died, the query that missed, and when.

    <trl>
    DEFINE RECORD gap CONTAINS RECORD death_node AND RECORD kind AND RECORD schema_version.
    </trl>
    """

    death_node: str
    query: str
    kind: str
    reason: str
    created_at: datetime
    gap_schema_version: str = GAP_SCHEMA_VERSION

    def as_dict(self) -> dict[str, str]:
        """Serialize to a flat JSON-friendly dict (``created_at`` as ISO-8601)."""
        raw = asdict(self)
        raw["created_at"] = self.created_at.isoformat()
        return raw


@runtime_checkable
class GapStore(Protocol):
    """A write-only-for-the-engine ledger of located gaps, TTL-bounded on read.

    Exposes no answer-authoring or corpus-writing surface — by construction (D8).
    """

    ttl: timedelta

    def record(self, gap: GapRecord) -> None:
        """Append ``gap`` to the ledger."""
        ...

    def gaps(self, *, now: datetime | None = None) -> list[GapRecord]:
        """Return an eager snapshot of un-expired gaps (older than ``ttl`` excluded)."""
        ...

    def prune(self, *, now: datetime | None = None) -> int:
        """Drop records older than ``ttl`` from ``now``; return the number removed."""
        ...


def _is_live(gap: GapRecord, ttl: timedelta, now: datetime) -> bool:
    return gap.created_at > now - ttl


@dataclass(slots=True)
class InMemoryGapStore:
    """In-process gap ledger (zero external deps), TTL-enforced on read + prune."""

    ttl: timedelta = DEFAULT_TTL
    _records: list[GapRecord] = field(default_factory=list)

    def record(self, gap: GapRecord) -> None:
        self._records.append(gap)

    def gaps(self, *, now: datetime | None = None) -> list[GapRecord]:
        moment = now if now is not None else datetime.now(tz=_tz(self._records))
        return [g for g in self._records if _is_live(g, self.ttl, moment)]

    def prune(self, *, now: datetime | None = None) -> int:
        moment = now if now is not None else datetime.now(tz=_tz(self._records))
        before = len(self._records)
        self._records = [g for g in self._records if _is_live(g, self.ttl, moment)]
        return before - len(self._records)


@dataclass(slots=True)
class JsonFileGapStore:
    """Gap ledger persisted as a JSON-lines-shaped array file (mirrors the stores/ pattern)."""

    path: Path
    ttl: timedelta = DEFAULT_TTL

    def record(self, gap: GapRecord) -> None:
        records = self._read()
        records.append(gap)
        self._flush(records)

    def gaps(self, *, now: datetime | None = None) -> list[GapRecord]:
        records = self._read()
        moment = now if now is not None else datetime.now(tz=_tz(records))
        return [g for g in records if _is_live(g, self.ttl, moment)]

    def prune(self, *, now: datetime | None = None) -> int:
        records = self._read()
        moment = now if now is not None else datetime.now(tz=_tz(records))
        live = [g for g in records if _is_live(g, self.ttl, moment)]
        removed = len(records) - len(live)
        if removed:
            self._flush(live)
        return removed

    def _read(self) -> list[GapRecord]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [
            GapRecord(
                death_node=str(item["death_node"]),
                query=str(item["query"]),
                kind=str(item["kind"]),
                reason=str(item["reason"]),
                created_at=datetime.fromisoformat(str(item["created_at"])),
                gap_schema_version=str(item.get("gap_schema_version", GAP_SCHEMA_VERSION)),
            )
            for item in raw
        ]

    def _flush(self, records: list[GapRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [g.as_dict() for g in records]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _tz(records: list[GapRecord]) -> tzinfo | None:
    """Match ``now``'s awareness to the stored records (all-aware or all-naive in practice)."""
    if records and records[0].created_at.tzinfo is not None:
        return records[0].created_at.tzinfo
    return None
