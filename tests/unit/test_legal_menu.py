"""SP-B legal_menu tests (AAA #69, Phase-7 rows 13-14): the single legality oracle (ADR-004, B6).

``legal_menu`` is the sole session-gated legality gate; ``Engine._enumerate`` delegates to it,
so the engine's gate and the checker's (SP-E ``verify_trace``) gate cannot drift.
"""

from __future__ import annotations

from pathlib import Path

from noise_chatbot.engine import Engine, ScriptedSelector, Session, legal_menu
from tests.unit._engine_helpers import faq_corpus


def test_legal_menu_excludes_protected_for_anon(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    ids = [option.node_id for option in legal_menu(corpus, "topics", Session.anonymous())]
    assert "locked" not in ids  # protected, session lacks the capability
    assert ids == ["about", "deep_none", "proc"]


def test_legal_menu_includes_protected_with_capability(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    session = Session(frozenset({"locked"}))
    ids = [option.node_id for option in legal_menu(corpus, "topics", session)]
    assert ids == ["about", "deep_none", "locked", "proc"]


def test_legal_menu_never_leaks_via_ungated_children(tmp_path: Path) -> None:
    # Corpus.children is ungated and DOES expose the protected node; legal_menu must not.
    corpus = faq_corpus(tmp_path)
    ungated = {child.id for child in corpus.children("topics")}
    gated = {option.node_id for option in legal_menu(corpus, "topics", Session.anonymous())}
    assert "locked" in ungated and "locked" not in gated


def test_enumerate_delegates_to_legal_menu(tmp_path: Path) -> None:
    # Every node x {anon, capability}: the private engine gate == the public oracle (one source).
    corpus = faq_corpus(tmp_path)
    engine = Engine(corpus, ScriptedSelector([]))
    for node_id in corpus.nodes:
        for session in (Session.anonymous(), Session(frozenset({"locked"}))):
            assert engine._enumerate(node_id, session) == legal_menu(corpus, node_id, session)
