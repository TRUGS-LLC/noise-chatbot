"""SP2 GapStore tests (T2.4) — located capture, versioned, TTL-bounded, never-composing.

Verifies ``WRITE gap WHEN bottom_route EXISTS`` + ``gap_store SHALL REQUIRE ttl_config``
+ ``gap_store SHALL REQUIRE schema_version`` + capture-never-compose (D8). The static
never-compose half is completed by the Phase 8 CG-1 scan; here we assert the store's API
exposes no answer-authoring surface and enforces TTL.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from noise_chatbot.stores.gap import (
    GAP_SCHEMA_VERSION,
    KIND_ROOT_BOTTOM,
    GapRecord,
    GapStore,
    InMemoryGapStore,
    JsonFileGapStore,
)

_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
_TTL = timedelta(days=90)


@pytest.fixture(params=["memory", "jsonfile"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> GapStore:
    if request.param == "memory":
        return InMemoryGapStore(ttl=_TTL)
    return JsonFileGapStore(path=tmp_path / "gaps.json", ttl=_TTL)


def _gap(when: datetime, *, death_node: str = "root") -> GapRecord:
    return GapRecord(
        death_node=death_node,
        query="what is the meaning of life",
        kind=KIND_ROOT_BOTTOM,
        reason="off-menu",
        created_at=when,
    )


def test_record_then_read_carries_version_and_kind(store: GapStore) -> None:
    store.record(_gap(_NOW))
    gaps = store.gaps(now=_NOW)
    assert len(gaps) == 1
    assert gaps[0].gap_schema_version == GAP_SCHEMA_VERSION == "1"
    assert gaps[0].kind == KIND_ROOT_BOTTOM
    assert gaps[0].death_node == "root"


def test_ttl_excludes_and_prunes_expired_records(store: GapStore) -> None:
    store.record(_gap(_NOW - timedelta(days=100), death_node="old"))  # expired (> 90d)
    store.record(_gap(_NOW - timedelta(days=1), death_node="fresh"))  # live

    live = store.gaps(now=_NOW)
    assert [g.death_node for g in live] == ["fresh"]  # expired excluded on read

    removed = store.prune(now=_NOW)
    assert removed == 1
    assert [g.death_node for g in store.gaps(now=_NOW)] == ["fresh"]
    assert store.prune(now=_NOW) == 0  # idempotent


def test_store_requires_a_ttl(store: GapStore) -> None:
    # ttl_config is a required attribute of every GapStore (the D8 retention rider)
    assert isinstance(store.ttl, timedelta)


def test_gap_record_exposes_no_answer_authoring_surface() -> None:
    # capture-never-compose (D8): a gap record indexes a miss; it carries no answer text,
    # and the store has no compose/answer/respond method.
    field_names = {f.name for f in fields(GapRecord)}
    assert "answer" not in field_names
    assert "answer_text" not in field_names
    assert field_names == {
        "death_node",
        "query",
        "kind",
        "reason",
        "created_at",
        "gap_schema_version",
    }
    for forbidden in ("compose", "answer", "respond", "generate"):
        assert not hasattr(InMemoryGapStore, forbidden)
        assert not hasattr(JsonFileGapStore, forbidden)


def test_jsonfile_store_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "gaps.json"
    JsonFileGapStore(path=path, ttl=_TTL).record(_gap(_NOW))
    # a fresh instance reads the same file
    reopened = JsonFileGapStore(path=path, ttl=_TTL)
    gaps = reopened.gaps(now=_NOW)
    assert len(gaps) == 1
    assert gaps[0].created_at == _NOW
