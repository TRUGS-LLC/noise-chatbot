"""SP4 adapter tests (T4.2) — Classifier conformance + fail-honest (ADR-005).

The adapter implements the ``Classifier`` contract exactly: it returns node **ids, never
composed text**. An engine exception yields an honest empty result (the server's no-match
reply), never a crash and never a silent fallback to the flat keyword classifier.
"""

from __future__ import annotations

from pathlib import Path

from noise_chatbot.engine import Engine, ScriptedSelector
from noise_chatbot.engine.adapter import as_classifier
from noise_chatbot.engine.select.port import Menu
from tests.unit._engine_helpers import faq_corpus


class _RaisingSelector:
    """A backend that always raises — to exercise the adapter's fail-honest path."""

    def select(self, query: str, menu: Menu) -> str:
        raise RuntimeError("backend exploded")


def test_adapter_returns_ids_only(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    engine = Engine(corpus, ScriptedSelector(["topics", "about"]))
    classify = as_classifier(engine)

    ids = classify("what is trugs?", [])  # the server's nodes list is not consulted

    assert ids == ["about"]  # the delivered leaf's id — an id, not composed text
    assert all(isinstance(node_id, str) for node_id in ids)


def test_adapter_reports_the_bottom_id_on_a_miss(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    engine = Engine(corpus, ScriptedSelector(["x", "x"]))  # off-menu → root ⊥
    classify = as_classifier(engine)
    assert classify("???", []) == ["root_none"]


def test_adapter_is_fail_honest_on_engine_exception(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    engine = Engine(corpus, _RaisingSelector())
    classify = as_classifier(engine)

    # engine raises → honest empty result, no crash, no silent flat-classifier fallback
    assert classify("anything", []) == []
