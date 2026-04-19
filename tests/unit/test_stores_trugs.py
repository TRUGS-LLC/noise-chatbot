"""Conformance + impl tests for the ``Trugs*`` store adapters.

<trl>
STAGE test_stores_trugs SHALL VALIDATE RECORD TrugsGuardrailStore
    AND RECORD TrugsResponseStore AND RECORD TrugsBannedKeyStore
    AND RECORD TrugsKnowledgeBaseStore.
</trl>

Skipped entirely when the ``[trugs]`` optional extra is absent —
``pytest.importorskip`` handles module unavailability at collection time.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

# If the [trugs] extra isn't installed, skip the entire module at collection.
pytest.importorskip("trugs_store")

from trugs_store import InMemoryGraphStore

from noise_chatbot.stores import BannedKeyStore
from noise_chatbot.stores.protocols import (
    GuardrailStore,
    KnowledgeBaseStore,
    ResponseStore,
)
from noise_chatbot.stores.trugs import (
    TrugsBannedKeyStore,
    TrugsGuardrailStore,
    TrugsKnowledgeBaseStore,
    TrugsResponseStore,
)
from tests.unit._store_suite import (
    BannedKeyStoreSuite,
    GuardrailStoreSuite,
    KnowledgeBaseStoreSuite,
    ResponseStoreSuite,
)


def _empty_graph() -> InMemoryGraphStore:
    """Build a fresh empty trugs_store graph for a fixture factory."""
    g = InMemoryGraphStore()
    g.set_metadata("name", "test-graph")
    g.set_metadata("version", "1.0.0")
    g.set_metadata("type", "TRACKER")
    return g


def _graph_with_nodes(nodes: list[dict[str, object]]) -> InMemoryGraphStore:
    """Build a graph and populate with the given node dicts."""
    g = _empty_graph()
    for n in nodes:
        g.add_node(n)
    return g


# ── TrugsGuardrailStore ────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS trugsguardrailstore.
class TestTrugsGuardrailStore(GuardrailStoreSuite):
    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    @staticmethod
    def store_factory() -> TrugsGuardrailStore:
        return TrugsGuardrailStore(_empty_graph())

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(TrugsGuardrailStore(_empty_graph()), GuardrailStore)

    # AGENT SHALL VALIDATE PROCESS reads_guardrail_nodes.
    def test_reads_guardrail_nodes(self) -> None:
        """Nodes of the configured type with a ``response`` property become ResponseNodes."""
        g = _graph_with_nodes(
            [
                {
                    "id": "guard-1",
                    "type": "GUARDRAIL",
                    "parent_id": None,
                    "contains": [],
                    "properties": {
                        "name": "Identity",
                        "keywords": ["your name", "who are you"],
                        "response": "I'm a chatbot.",
                    },
                    "metric_level": "BASE_GUARD",
                    "dimension": "guardrails",
                },
                {
                    "id": "other",
                    "type": "DOCUMENT",  # not a GUARDRAIL → skipped
                    "parent_id": None,
                    "contains": [],
                    "properties": {"response": "SHOULD_NOT_APPEAR"},
                    "metric_level": "BASE_DOC",
                    "dimension": "docs",
                },
            ]
        )
        store = TrugsGuardrailStore(g)
        gs = store.guardrails()
        assert len(gs) == 1
        assert gs[0].id == "guard-1"

    # AGENT SHALL VALIDATE PROCESS configurable_node_type.
    def test_configurable_node_type(self) -> None:
        """``node_type`` constructor arg selects which graph nodes count."""
        g = _graph_with_nodes(
            [
                {
                    "id": "custom-1",
                    "type": "CUSTOM_GUARD",
                    "parent_id": None,
                    "contains": [],
                    "properties": {"response": "custom guard"},
                    "metric_level": "BASE_GUARD",
                    "dimension": "guardrails",
                }
            ]
        )
        store = TrugsGuardrailStore(g, node_type="CUSTOM_GUARD")
        assert len(store.guardrails()) == 1


# ── TrugsResponseStore ─────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS trugsresponsestore.
class TestTrugsResponseStore(ResponseStoreSuite):
    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    @staticmethod
    def store_factory() -> TrugsResponseStore:
        return TrugsResponseStore(_empty_graph())

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(TrugsResponseStore(_empty_graph()), ResponseStore)

    # AGENT SHALL VALIDATE PROCESS reads_response_nodes.
    def test_reads_response_nodes(self) -> None:
        g = _graph_with_nodes(
            [
                {
                    "id": "pricing",
                    "type": "RESPONSE",
                    "parent_id": None,
                    "contains": [],
                    "properties": {
                        "name": "Pricing",
                        "keywords": ["price", "cost"],
                        "response": "Our plans start at $10/mo.",
                    },
                    "metric_level": "BASE_RESP",
                    "dimension": "responses",
                }
            ]
        )
        store = TrugsResponseStore(g)
        rs = store.responses()
        assert len(rs) == 1
        assert rs[0].id == "pricing"
        # ``name`` gets appended to keywords for better matching
        assert "Pricing" in rs[0].keywords


# ── TrugsBannedKeyStore ────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS trugsbannedkeystore.
class TestTrugsBannedKeyStore(BannedKeyStoreSuite):
    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    @staticmethod
    def store_factory() -> TrugsBannedKeyStore:
        return TrugsBannedKeyStore(_empty_graph(), ttl=timedelta(hours=1))

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(TrugsBannedKeyStore(_empty_graph()), BannedKeyStore)

    # AGENT SHALL VALIDATE PROCESS default_ttl_72h.
    def test_default_ttl_72h(self) -> None:
        assert TrugsBannedKeyStore(_empty_graph()).ttl == timedelta(hours=72)

    # AGENT SHALL VALIDATE PROCESS ban_writes_graph_node.
    def test_ban_writes_graph_node(self) -> None:
        """A ban adds a BAN-type node to the underlying graph."""
        g = _empty_graph()
        store = TrugsBannedKeyStore(g, ttl=timedelta(hours=1))
        store.ban("abc123", when=datetime(2026, 1, 1, 12, 0, 0))
        node = g.get_node("abc123")
        assert node is not None
        assert node["type"] == "BAN"
        assert node["properties"]["banned_at"] == "2026-01-01T12:00:00"

    # AGENT SHALL VALIDATE PROCESS mutates_shared_graph.
    def test_mutates_shared_graph(self) -> None:
        """Caller-supplied graph is mutated in place (caller controls persistence)."""
        g = _empty_graph()
        assert g.node_count() == 0
        store = TrugsBannedKeyStore(g)
        store.ban("abc")
        assert g.node_count() == 1
        store.unban("abc")
        assert g.node_count() == 0

    # AGENT SHALL VALIDATE PROCESS corrupt_ban_node_ignored.
    def test_corrupt_ban_node_ignored(self) -> None:
        """A BAN node with missing or invalid banned_at is treated as not-banned."""
        g = _graph_with_nodes(
            [
                {
                    "id": "corrupt-key",
                    "type": "BAN",
                    "parent_id": None,
                    "contains": [],
                    "properties": {"banned_at": "not-an-iso-date"},
                    "metric_level": "BASE_BAN",
                    "dimension": "ban_tracking",
                }
            ]
        )
        store = TrugsBannedKeyStore(g)
        assert store.is_banned("corrupt-key") is False


# ── TrugsKnowledgeBaseStore ────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS trugsknowledgebasestore.
class TestTrugsKnowledgeBaseStore(KnowledgeBaseStoreSuite):
    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    @staticmethod
    def store_factory() -> TrugsKnowledgeBaseStore:
        # Fresh instance from a nonexistent path — returns None context.
        return TrugsKnowledgeBaseStore("/nonexistent/path/kb.trug.json")

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(TrugsKnowledgeBaseStore("/nonexistent.json"), KnowledgeBaseStore)

    # AGENT SHALL VALIDATE PROCESS accepts_prebuilt_dict.
    def test_accepts_prebuilt_dict(self) -> None:
        """A dict source is used verbatim (bypasses read_trug)."""
        payload: dict[str, object] = {"name": "Prebuilt", "nodes": []}
        store = TrugsKnowledgeBaseStore(payload)
        assert store.context() == payload

    # AGENT SHALL VALIDATE PROCESS reads_valid_trug_file.
    def test_reads_valid_trug_file(self, tmp_path: Path) -> None:
        """A valid TRUG JSON file is read through trugs_store.read_trug."""
        import json

        trug = {
            "name": "KB",
            "version": "1.0.0",
            "type": "TRACKER",
            "nodes": [],
            "edges": [],
        }
        p = tmp_path / "kb.trug.json"
        p.write_text(json.dumps(trug))
        store = TrugsKnowledgeBaseStore(p)
        ctx = store.context()
        assert ctx is not None
        assert ctx["name"] == "KB"
