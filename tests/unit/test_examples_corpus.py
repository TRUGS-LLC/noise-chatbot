"""SP4 demo-corpus lint (T4.1) — the D10 dogfood FAQ is VALID, versioned, ⊥-total.

Verifies the ``examples/faq_demo`` corpus is ``trug validate``-VALID (real gate, skipped
where the CLI is absent), carries ``schema_version``, and has an authored bottom reachable
from every menu (so no fork can strand a user without a located ⊥).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from noise_chatbot.corpus import ROLE_BOTTOM, ROLE_BRANCH, Corpus, load_corpus

_DEMO = Path(__file__).parents[2] / "examples" / "faq_demo" / "faq.trug.json"


def _passthru(path: Path) -> None:
    """Structural checks don't need the trug CLI."""


def _has_reachable_bottom(corpus: Corpus, node_id: str) -> bool:
    """Walk ancestors (incl. the node) for any bottom child — the engine's ⊥ routing."""
    current: str | None = node_id
    while current is not None:
        if any(child.role == ROLE_BOTTOM for child in corpus.children(current)):
            return True
        current = corpus.node(current).parent_id
    return False


def test_demo_corpus_parses_and_is_versioned() -> None:
    corpus = load_corpus(_DEMO, validator=_passthru)
    assert corpus.schema_version == "1"
    assert corpus.root.role == ROLE_BRANCH
    # sanity: the dogfood answers are present
    assert corpus.node("what_is_trugs").role == "answer"
    assert "Noise_IK" in (corpus.node("crypto").answer_text or "")


def test_every_menu_has_a_reachable_bottom() -> None:
    corpus = load_corpus(_DEMO, validator=_passthru)
    branches_with_menu = [
        node.id for node in corpus.nodes.values() if node.role == ROLE_BRANCH and node.contains
    ]
    assert branches_with_menu  # there is at least the root
    for branch_id in branches_with_menu:
        assert _has_reachable_bottom(corpus, branch_id), f"menu {branch_id!r} strands users"


@pytest.mark.skipif(
    shutil.which("trug") is None,
    reason="requires the published trug CLI (pip install noise-chatbot[engine])",
)
def test_demo_corpus_passes_the_real_trug_gate() -> None:
    # default validator = the real published `trug validate`
    corpus = load_corpus(_DEMO)
    assert corpus.root_id == "root"
