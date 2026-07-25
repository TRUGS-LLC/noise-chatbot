"""SP-C wire-provenance tests (AAA #69, Phase-7 rows 18-19, 22): out-of-band, classifier untouched.

Provenance rides an ``omitempty`` ``Message`` field (mirroring ``reply_to``) — absent bytes when
unset, so parity fixtures stay green — and the engine adapter carries it out-of-band through a
per-call thread-local channel, keeping ``classify``'s ``-> list[str]`` return (the ``Classifier``
``Callable`` contract is never widened). These tests need no server / Noise transport.
"""

from __future__ import annotations

import threading
from pathlib import Path

from noise_chatbot.engine import Engine
from noise_chatbot.engine.adapter import as_classifier, provenance_of
from noise_chatbot.engine.select.port import Menu
from noise_chatbot.protocol.message import Message
from tests.unit._engine_helpers import faq_corpus


class _FirstSelector:
    """A deterministic, reusable backend: always descend the first legal option (root→topics→about)."""

    def select(self, query: str, menu: Menu) -> str:
        return menu[0].node_id


# ── Message omitempty (rows 18, 22) — parity-safe wire ───────────────────────────────
def test_to_json_omits_provenance_when_unset() -> None:
    doc = Message(type="CHAT", payload={"text": "hi"}, id="1").to_json()
    assert "provenance" not in doc  # byte-identical to a pre-SP-C envelope (parity fixtures green)


def test_provenance_round_trips_when_set() -> None:
    prov = {"corpus_digest": "tci1-sha256-abc", "address": ["root", "topics", "about"]}
    msg = Message(type="CHAT", payload={"text": "hi"}, id="1", provenance=prov)
    assert '"provenance"' in msg.to_json()
    assert Message.from_json(msg.to_json()).provenance == prov


def test_from_json_without_provenance_defaults_none() -> None:
    # A Go/legacy envelope with no provenance key parses cleanly (nil-tolerant boundary).
    assert Message.from_json('{"type":"CHAT","payload":{"text":"x"},"id":"1"}').provenance is None


# ── out-of-band adapter channel (rows 19) — contract not widened ─────────────────────
def test_adapter_carries_provenance_out_of_band(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    classify = as_classifier(Engine(corpus, _FirstSelector()))
    ids = classify("hi", [])
    assert ids == ["about"]  # -> list[str]: the delivered leaf id, contract intact
    prov = provenance_of(classify)
    assert prov is not None
    assert prov["corpus_digest"] == corpus.corpus_digest
    assert prov["address"] == ["root", "topics", "about"]
    assert prov["address"][-1] == ids[0]  # RT-2: the wire address leaf == the delivered leaf


def test_provenance_of_clears_after_read(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    classify = as_classifier(Engine(corpus, _FirstSelector()))
    classify("hi", [])
    assert provenance_of(classify) is not None
    assert provenance_of(classify) is None  # take-once: no stale carry to the next request


def test_provenance_of_is_none_for_non_engine_classifier() -> None:
    # Adapter-identity check: a plain classifier (no registered channel) carries no provenance.
    def keyword_classify(user_text: str, nodes: list[object]) -> list[str]:
        return []

    assert provenance_of(keyword_classify) is None


def test_provenance_channel_is_thread_local(tmp_path: Path) -> None:
    # The worker thread's classify sets ITS OWN provenance; the main thread (which never called
    # classify) sees None — proving concurrent connection threads never cross provenance.
    corpus = faq_corpus(tmp_path)
    classify = as_classifier(Engine(corpus, _FirstSelector()))
    captured: dict[str, object] = {}

    def worker() -> None:
        classify("hi", [])
        captured["prov"] = provenance_of(classify)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert captured["prov"] is not None  # the worker captured its own walk
    assert provenance_of(classify) is None  # main thread's slot is untouched (thread-local)
