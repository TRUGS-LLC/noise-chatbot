"""Unit tests for ``Server`` builder methods (config accumulation, no I/O).

<trl>
STAGE test_server_builders SHALL VALIDATE SERVICE Server SUBJECT_TO
    RECORD builder_config.
EACH FUNCTION with_* SHALL RETURN SELF AND SHALL BIND DATA input.
</trl>

Covers the pure-config surface — builders mutate server state and return
``self``. No sockets, no threads, no cryptography.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from noise_chatbot.server.server import (
    LLMConfig,
    ResponseNode,
    SafetyConfig,
    Server,
)


# AGENT SHALL VALIDATE PROCESS init_sets_defaults.
def test_init_sets_defaults() -> None:
    """Fresh ``Server`` has a keypair, default safety config, default guardrails."""
    s = Server("127.0.0.1:0")
    assert len(s.key().public) == 32
    assert len(s.key().private) == 32
    assert s.get_responses() == []
    assert s._safety.max_input_bytes == 2000
    assert s._safety.max_input_tokens == 200
    # 15 bundled guardrail nodes (see guardrails.py)
    assert len(s._guardrails) == 15


# AGENT SHALL VALIDATE PROCESS with_safety_replaces_config.
def test_with_safety_replaces_config() -> None:
    """``with_safety`` installs a new SafetyConfig wholesale."""
    custom = SafetyConfig(
        max_input_tokens=50,
        max_input_bytes=500,
        rate_limit=5,
        session_timeout=timedelta(minutes=5),
        greeting="hi",
        confidence_min=2,
    )
    s = Server("127.0.0.1:0").with_safety(custom)
    assert s._safety is custom
    assert s._safety.max_input_tokens == 50


# AGENT SHALL VALIDATE PROCESS with_greeting_mutates_safety.
def test_with_greeting_mutates_safety() -> None:
    """``with_greeting`` writes into the current SafetyConfig."""
    s = Server("127.0.0.1:0").with_greeting("welcome")
    assert s._safety.greeting == "welcome"


# AGENT SHALL VALIDATE PROCESS with_no_match_sets_text.
def test_with_no_match_sets_text() -> None:
    """``with_no_match`` sets the no-match fallback text."""
    s = Server("127.0.0.1:0").with_no_match("nope")
    assert s._no_match_text == "nope"


# AGENT SHALL VALIDATE PROCESS with_contact_footer_sets_text.
def test_with_contact_footer_sets_text() -> None:
    """``with_contact_footer`` sets the footer appended to responses."""
    s = Server("127.0.0.1:0").with_contact_footer("contact@example.com")
    assert s._contact_footer == "contact@example.com"


# AGENT SHALL VALIDATE PROCESS with_responses_stores_nodes.
def test_with_responses_stores_nodes() -> None:
    """``with_responses`` replaces the response-node list."""
    nodes = [ResponseNode(id="a", keywords=["x"], response="A")]
    s = Server("127.0.0.1:0").with_responses(nodes)
    assert s.get_responses() == nodes


# AGENT SHALL VALIDATE PROCESS with_llm_stores_config.
def test_with_llm_stores_config() -> None:
    """``with_llm`` stores an ``LLMConfig`` record (not auto-wired)."""
    s = Server("127.0.0.1:0").with_llm("openai", "gpt-4", "OPENAI_API_KEY")
    assert isinstance(s._llm_config, LLMConfig)
    assert s._llm_config.provider == "openai"
    assert s._llm_config.model == "gpt-4"


# AGENT SHALL VALIDATE PROCESS with_upstream_stores_addr_and_key.
def test_with_upstream_stores_addr_and_key() -> None:
    """``with_upstream`` stores upstream server addr + pubkey."""
    s = Server("127.0.0.1:0").with_upstream("1.2.3.4:5000", "ff" * 32)
    assert s._upstream_addr == "1.2.3.4:5000"
    assert s._upstream_key == "ff" * 32


# AGENT SHALL VALIDATE PROCESS builders_return_self_for_chaining.
def test_builders_return_self_for_chaining() -> None:
    """Every builder returns the Server instance for method chaining."""
    s = Server("127.0.0.1:0")
    chain = (
        s.with_greeting("hi")
        .with_no_match("nope")
        .with_contact_footer("x@y")
        .with_llm("openai", "gpt-4", "OPENAI_API_KEY")
        .with_upstream("1.2.3.4:5000", "ff" * 32)
    )
    assert chain is s


# AGENT SHALL VALIDATE PROCESS on_chat_registers_handler.
def test_on_chat_registers_handler() -> None:
    """``on_chat`` installs a chat-handler callable."""

    def handler(text: str) -> str:
        return text.upper()

    s = Server("127.0.0.1:0").on_chat(handler)
    assert s._chat_handler is handler


# AGENT SHALL VALIDATE PROCESS on_analytics_registers_callback.
def test_on_analytics_registers_callback() -> None:
    """``on_analytics`` installs an analytics callback."""
    calls: list[object] = []

    def cb(stats: object, text: str, ids: list[str]) -> None:
        calls.append((stats, text, ids))

    s = Server("127.0.0.1:0").on_analytics(cb)
    assert s._on_analytics is cb


# AGENT SHALL VALIDATE PROCESS with_classifier_registers_primary.
def test_with_classifier_registers_primary() -> None:
    """``with_classifier`` installs the primary classifier."""

    def cls(text: str, nodes: list[ResponseNode]) -> list[str]:
        return []

    s = Server("127.0.0.1:0").with_classifier(cls)
    assert s._classifier is cls


# AGENT SHALL VALIDATE PROCESS public_key_matches_key.
def test_public_key_matches_key() -> None:
    """``public_key()`` returns a 64-char hex encoding of ``key().public``."""
    s = Server("127.0.0.1:0")
    h = s.public_key()
    assert len(h) == 64
    assert bytes.fromhex(h) == s.key().public


# AGENT SHALL VALIDATE PROCESS get_trug_context_empty_when_unset.
def test_get_trug_context_empty_when_unset() -> None:
    """With no TRUG loaded, ``get_trug_context()`` returns an empty string."""
    s = Server("127.0.0.1:0")
    assert s.get_trug_context() == ""


# AGENT SHALL VALIDATE PROCESS with_trug_loads_json.
def test_with_trug_loads_json(tmp_path: Path) -> None:
    """``with_trug`` parses a JSON file into ``_trug_data``."""
    trug = {
        "nodes": [
            {
                "id": "n1",
                "properties": {"name": "Hours", "description": "9-5 M-F"},
            }
        ]
    }
    path = tmp_path / "k.trug.json"
    path.write_text(json.dumps(trug))
    s = Server("127.0.0.1:0").with_trug(path)
    ctx = s.get_trug_context()
    assert "Hours" in ctx
    assert "9-5 M-F" in ctx


# AGENT SHALL VALIDATE PROCESS with_trug_missing_file_is_silent.
def test_with_trug_missing_file_is_silent(tmp_path: Path) -> None:
    """Missing TRUG file does not raise; ``_trug_data`` stays ``None``."""
    s = Server("127.0.0.1:0").with_trug(tmp_path / "missing.trug.json")
    assert s._trug_data is None
    assert s.get_trug_context() == ""


# AGENT SHALL VALIDATE PROCESS with_trug_invalid_json_is_silent.
def test_with_trug_invalid_json_is_silent(tmp_path: Path) -> None:
    """Malformed JSON does not raise; ``_trug_data`` stays ``None``."""
    path = tmp_path / "bad.trug.json"
    path.write_text("{not json")
    s = Server("127.0.0.1:0").with_trug(path)
    assert s._trug_data is None


# AGENT SHALL VALIDATE PROCESS with_responses_from_trug_loads_nodes.
def test_with_responses_from_trug_loads_nodes(tmp_path: Path) -> None:
    """``with_responses_from_trug`` reads response nodes from a TRUG file."""
    trug = {
        "nodes": [
            {
                "id": "n1",
                "properties": {
                    "name": "Pricing",
                    "description": "Our plans start at $10/mo.",
                    "keywords": ["price", "pricing", "cost"],
                    "response": "Our plans start at $10/mo.",
                },
            },
            {
                "id": "n2",
                "properties": {
                    "name": "Empty",
                    "description": "",
                    # No response → node is skipped
                },
            },
        ]
    }
    path = tmp_path / "responses.trug.json"
    path.write_text(json.dumps(trug))
    s = Server("127.0.0.1:0").with_responses_from_trug(path)
    assert len(s.get_responses()) == 1
    assert s.get_responses()[0].id == "n1"
    assert "price" in s.get_responses()[0].keywords
    # ``name`` is appended to keywords
    assert "Pricing" in s.get_responses()[0].keywords


# AGENT SHALL VALIDATE PROCESS with_guardrails_appends_nodes.
def test_with_guardrails_appends_nodes(tmp_path: Path) -> None:
    """``with_guardrails`` appends custom guardrail nodes to the defaults."""
    trug = {
        "nodes": [
            {
                "id": "custom-guard",
                "properties": {
                    "keywords": ["refund"],
                    "response": "Refund policy: contact support.",
                },
            }
        ]
    }
    path = tmp_path / "custom.trug.json"
    path.write_text(json.dumps(trug))
    before = len(Server("127.0.0.1:0")._guardrails)
    s = Server("127.0.0.1:0").with_guardrails(path)
    assert len(s._guardrails) == before + 1
    assert s._guardrails[-1].response.startswith("Refund policy")


# AGENT SHALL VALIDATE PROCESS stop_sets_event.
def test_stop_sets_event() -> None:
    """``stop()`` sets the internal stop event even with no live listener."""
    s = Server("127.0.0.1:0")
    assert not s._stop.is_set()
    s.stop()
    assert s._stop.is_set()


# ── Store builders (Protocol-backed surface) ──────────────────────────


# AGENT SHALL VALIDATE PROCESS default_stores_are_in_memory.
def test_default_stores_are_in_memory() -> None:
    """Fresh Server has InMemory defaults for all four stores."""
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

    s = Server("127.0.0.1:0")
    assert isinstance(s._guardrail_store, InMemoryGuardrailStore)
    assert isinstance(s._response_store, InMemoryResponseStore)
    assert isinstance(s._banned_key_store, InMemoryBannedKeyStore)
    assert isinstance(s._knowledge_base_store, InMemoryKnowledgeBaseStore)
    # Runtime-checkable Protocol check
    assert isinstance(s._guardrail_store, GuardrailStore)
    assert isinstance(s._response_store, ResponseStore)
    assert isinstance(s._banned_key_store, BannedKeyStore)
    assert isinstance(s._knowledge_base_store, KnowledgeBaseStore)


# AGENT SHALL VALIDATE PROCESS with_guardrail_store_injects.
def test_with_guardrail_store_injects() -> None:
    """``with_guardrail_store`` replaces the default and syncs _guardrails."""
    from noise_chatbot.server.server import ResponseNode
    from noise_chatbot.stores import InMemoryGuardrailStore

    custom = InMemoryGuardrailStore(
        [ResponseNode(id="custom-1", keywords=["x"], response="CUSTOM")]
    )
    s = Server("127.0.0.1:0").with_guardrail_store(custom)
    assert s._guardrail_store is custom
    assert len(s._guardrails) == 1
    assert s._guardrails[0].id == "custom-1"


# AGENT SHALL VALIDATE PROCESS with_response_store_injects.
def test_with_response_store_injects() -> None:
    """``with_response_store`` replaces the default and syncs _responses."""
    from noise_chatbot.server.server import ResponseNode
    from noise_chatbot.stores import InMemoryResponseStore

    custom = InMemoryResponseStore([ResponseNode(id="pricing", keywords=["price"], response="$10")])
    s = Server("127.0.0.1:0").with_response_store(custom)
    assert s._response_store is custom
    assert s.get_responses()[0].id == "pricing"


# AGENT SHALL VALIDATE PROCESS with_banned_keys_injects.
def test_with_banned_keys_injects() -> None:
    """``with_banned_keys`` replaces the default ban store."""
    from datetime import timedelta

    from noise_chatbot.stores import InMemoryBannedKeyStore

    custom = InMemoryBannedKeyStore(ttl=timedelta(minutes=30))
    s = Server("127.0.0.1:0").with_banned_keys(custom)
    assert s._banned_key_store is custom
    assert s._banned_key_store.ttl == timedelta(minutes=30)


# AGENT SHALL VALIDATE PROCESS with_knowledge_base_injects.
def test_with_knowledge_base_injects() -> None:
    """``with_knowledge_base`` replaces the default KB store and syncs _trug_data."""
    from noise_chatbot.stores import InMemoryKnowledgeBaseStore

    payload: dict[str, object] = {"name": "KB-test", "nodes": []}
    s = Server("127.0.0.1:0").with_knowledge_base(InMemoryKnowledgeBaseStore(payload))
    assert s._trug_data == payload


# AGENT SHALL VALIDATE PROCESS legacy_path_wrappers_still_work.
def test_legacy_path_wrappers_still_work(tmp_path: Path) -> None:
    """Regression: with_trug(path) / with_responses_from_trug(path) still work
    through the new JsonFile* store wrappers (R1 mitigation per LAB_1596)."""
    trug = {"nodes": [{"id": "n1", "properties": {"name": "Hours", "description": "9-5"}}]}
    p = tmp_path / "kb.json"
    p.write_text(json.dumps(trug))
    s = Server("127.0.0.1:0").with_trug(p)
    # Legacy getter still works
    assert "Hours" in s.get_trug_context()
    # New store also reflects the load
    assert s._knowledge_base_store.context() == trug


# AGENT SHALL VALIDATE PROCESS banned_key_store_ttl_enforced.
def test_banned_key_store_ttl_enforced() -> None:
    """Default BannedKeyStore uses the Go parity 72h TTL."""
    from datetime import timedelta

    s = Server("127.0.0.1:0")
    assert s._banned_key_store.ttl == timedelta(hours=72)
