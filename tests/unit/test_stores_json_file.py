"""Concrete conformance tests for the ``JsonFile*`` stores.

<trl>
STAGE test_stores_json_file SHALL VALIDATE RECORD JsonFileResponseStore
    AND RECORD JsonFileBannedKeyStore AND RECORD JsonFileKnowledgeBaseStore.
</trl>

The conformance tests in ``_store_suite`` exercise the Protocol contracts;
this file adds impl-specific tests (file I/O, persistence, corruption
recovery, atomic writes).
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from noise_chatbot.stores import (
    BannedKeyStore,
    JsonFileBannedKeyStore,
    JsonFileKnowledgeBaseStore,
    JsonFileResponseStore,
    KnowledgeBaseStore,
    ResponseStore,
)
from tests.unit._store_suite import (
    BannedKeyStoreSuite,
    KnowledgeBaseStoreSuite,
    ResponseStoreSuite,
)

# ── JsonFileResponseStore ──────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS jsonfileresponsestore.
class TestJsonFileResponseStore(ResponseStoreSuite):
    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    @staticmethod
    def store_factory() -> JsonFileResponseStore:
        # Empty store — points at a nonexistent path; silent-skip yields empty list.
        return JsonFileResponseStore("/nonexistent/path/responses.trug.json")

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(JsonFileResponseStore("/nonexistent.json"), ResponseStore)

    # AGENT SHALL VALIDATE PROCESS missing_file_is_silent.
    def test_missing_file_is_silent(self, tmp_path: Path) -> None:
        """Missing path yields empty responses, no raise."""
        store = JsonFileResponseStore(tmp_path / "nope.json")
        assert store.responses() == []

    # AGENT SHALL VALIDATE PROCESS malformed_json_is_silent.
    def test_malformed_json_is_silent(self, tmp_path: Path) -> None:
        """Malformed JSON yields empty responses, no raise."""
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        store = JsonFileResponseStore(p)
        assert store.responses() == []

    # AGENT SHALL VALIDATE PROCESS reads_response_nodes.
    def test_reads_response_nodes(self, tmp_path: Path) -> None:
        """Nodes with ``properties.response`` become ResponseNodes."""
        trug = {
            "nodes": [
                {
                    "id": "pricing",
                    "properties": {
                        "name": "Pricing",
                        "keywords": ["price", "cost"],
                        "response": "Our plans start at $10/mo.",
                    },
                },
                {
                    "id": "empty",
                    "properties": {"name": "Empty"},  # no response → skipped
                },
            ]
        }
        p = tmp_path / "responses.json"
        p.write_text(json.dumps(trug))
        store = JsonFileResponseStore(p)
        responses = store.responses()
        assert len(responses) == 1
        assert responses[0].id == "pricing"
        assert "price" in responses[0].keywords
        # ``name`` gets appended to keywords for better matching
        assert "Pricing" in responses[0].keywords


# ── JsonFileBannedKeyStore ─────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS jsonfilebannedkeystore.
class TestJsonFileBannedKeyStore(BannedKeyStoreSuite):
    # Share a tmp_path per test class instance via a factory.
    _tmp_counter: int = 0

    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    def store_factory(self) -> JsonFileBannedKeyStore:
        """Fresh temp file per test — avoids state bleed between cases."""
        TestJsonFileBannedKeyStore._tmp_counter += 1
        import tempfile

        tmpdir = Path(tempfile.mkdtemp(prefix="banstore_"))
        return JsonFileBannedKeyStore(
            tmpdir / f"bans_{TestJsonFileBannedKeyStore._tmp_counter}.json",
            ttl=timedelta(hours=1),
        )

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self, tmp_path: Path) -> None:
        store = JsonFileBannedKeyStore(tmp_path / "bans.json")
        assert isinstance(store, BannedKeyStore)

    # AGENT SHALL VALIDATE PROCESS default_ttl_72h.
    def test_default_ttl_72h(self, tmp_path: Path) -> None:
        assert JsonFileBannedKeyStore(tmp_path / "bans.json").ttl == timedelta(hours=72)

    # AGENT SHALL VALIDATE PROCESS persists_across_restart.
    def test_persists_across_restart(self, tmp_path: Path) -> None:
        """A ban recorded by one instance is visible to a fresh one reading the same file."""
        p = tmp_path / "bans.json"
        s1 = JsonFileBannedKeyStore(p, ttl=timedelta(hours=72))
        s1.ban("abc123")
        s2 = JsonFileBannedKeyStore(p, ttl=timedelta(hours=72))
        assert s2.is_banned("abc123") is True

    # AGENT SHALL VALIDATE PROCESS unban_persists.
    def test_unban_persists(self, tmp_path: Path) -> None:
        """Unban is also persisted."""
        p = tmp_path / "bans.json"
        s1 = JsonFileBannedKeyStore(p)
        s1.ban("abc")
        s1.unban("abc")
        s2 = JsonFileBannedKeyStore(p)
        assert s2.is_banned("abc") is False

    # AGENT SHALL VALIDATE PROCESS malformed_file_is_silent.
    def test_malformed_file_is_silent(self, tmp_path: Path) -> None:
        """Constructing against a corrupt file starts with empty bans, no raise."""
        p = tmp_path / "bans.json"
        p.write_text("{not json")
        store = JsonFileBannedKeyStore(p)
        assert store.is_banned("anything") is False

    # AGENT SHALL VALIDATE PROCESS atomic_write_parent_created.
    def test_atomic_write_parent_created(self, tmp_path: Path) -> None:
        """Parent dir is auto-created if missing."""
        p = tmp_path / "nested" / "dir" / "bans.json"
        store = JsonFileBannedKeyStore(p)
        store.ban("x")
        assert p.exists()
        # File is valid JSON
        data = json.loads(p.read_text())
        assert "x" in data


# ── JsonFileKnowledgeBaseStore ─────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS jsonfileknowledgebasestore.
class TestJsonFileKnowledgeBaseStore(KnowledgeBaseStoreSuite):
    # FUNCTION store_factory SHALL DEFINE RESOURCE.
    @staticmethod
    def store_factory() -> JsonFileKnowledgeBaseStore:
        return JsonFileKnowledgeBaseStore("/nonexistent/path/kb.trug.json")

    # AGENT SHALL VALIDATE PROCESS satisfies_protocol.
    def test_satisfies_protocol(self) -> None:
        assert isinstance(JsonFileKnowledgeBaseStore("/nonexistent.json"), KnowledgeBaseStore)

    # AGENT SHALL VALIDATE PROCESS reads_valid_trug.
    def test_reads_valid_trug(self, tmp_path: Path) -> None:
        trug = {"name": "KB", "nodes": [], "edges": []}
        p = tmp_path / "kb.json"
        p.write_text(json.dumps(trug))
        store = JsonFileKnowledgeBaseStore(p)
        ctx = store.context()
        assert ctx is not None
        assert ctx["name"] == "KB"

    # AGENT SHALL VALIDATE PROCESS missing_file_is_silent.
    def test_missing_file_is_silent(self, tmp_path: Path) -> None:
        store = JsonFileKnowledgeBaseStore(tmp_path / "nope.json")
        assert store.context() is None

    # AGENT SHALL VALIDATE PROCESS malformed_json_is_silent.
    def test_malformed_json_is_silent(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        store = JsonFileKnowledgeBaseStore(p)
        assert store.context() is None

    # AGENT SHALL VALIDATE PROCESS non_dict_root_is_silent.
    def test_non_dict_root_is_silent(self, tmp_path: Path) -> None:
        """JSON that parses to a list (not a dict) is rejected."""
        p = tmp_path / "bad.json"
        p.write_text("[1, 2, 3]")
        store = JsonFileKnowledgeBaseStore(p)
        assert store.context() is None
