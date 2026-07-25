"""SP-B trace-completeness tests (AAA #69, Phase-7 rows 9-12, 15): the self-contained v2 trace.

The v2 trace binds to a corpus (B1), records the session grant-set (B5) and the terminal
delivered leaf (B4) — so a third party can re-derive it. All additions are opt-in (B9).
"""

from __future__ import annotations

from pathlib import Path

from noise_chatbot.engine import Engine, ScriptedSelector, Session, TraceLog, TraceTerminal
from noise_chatbot.engine.trace import TRACE_SCHEMA_VERSION
from tests.unit._engine_helpers import faq_corpus


def test_trace_is_schema_v2(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    ans = Engine(corpus, ScriptedSelector(["topics", "about"])).answer("q")
    assert ans.trace.trace_schema_version == "2" == TRACE_SCHEMA_VERSION
    assert ans.trace.corpus_schema_version == "1"  # the corpus schema is untouched


def test_trace_binds_corpus_digest(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    ans = Engine(corpus, ScriptedSelector(["topics", "about"])).answer("q")
    assert ans.trace.corpus_digest == corpus.corpus_digest != ""


def test_trace_records_terminal_answer_leaf(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    ans = Engine(corpus, ScriptedSelector(["topics", "about"])).answer("q")
    assert ans.trace.terminal == TraceTerminal(leaf_id="about", is_bottom=False)
    assert ans.trace.terminal is not None
    assert ans.trace.terminal.leaf_id == ans.address[-1]  # bound to the delivered leaf, not text


def test_trace_records_terminal_bottom_leaf(tmp_path: Path) -> None:
    # Off-menu twice at `topics` routes to the deep-⊥ (deep_none); the terminal is that leaf.
    corpus = faq_corpus(tmp_path)
    ans = Engine(corpus, ScriptedSelector(["topics", "x", "x"])).answer("q")
    assert ans.is_bottom is True
    assert ans.trace.terminal is not None
    assert ans.trace.terminal.is_bottom is True
    assert ans.trace.terminal.leaf_id == ans.address[-1]


def test_trace_records_grant_set(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    anon = Engine(corpus, ScriptedSelector(["topics", "about"])).answer("q")
    assert anon.trace.grants == ()  # anonymous session
    granted = Engine(corpus, ScriptedSelector(["topics", "locked"])).answer(
        "q", session=Session(frozenset({"locked"}))
    )
    assert granted.trace.grants == ("locked",)


def test_digestless_tracelog_constructs_with_defaults() -> None:
    # B9: a digest-less trace still constructs — every new field is opt-in with a default.
    trace = TraceLog(corpus_schema_version="1")
    assert trace.corpus_digest == ""
    assert trace.grants == ()
    assert trace.terminal is None
    assert trace.steps == []


def test_legacy_v1_tracelog_still_validates() -> None:
    # A legacy v1 trace (explicit "1") constructs unchanged — the checker treats it as unbound.
    trace = TraceLog(corpus_schema_version="1", trace_schema_version="1")
    assert trace.trace_schema_version == "1"
    assert trace.corpus_digest == ""
