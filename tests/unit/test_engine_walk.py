"""SP2 engine-walk tests — the offline heart (T2.2 / 2.2b / 2.3 / 2.5 / 2.6 / 2.9 / 2.10).

All offline: deterministic mock backends, no network / keys / weights. Verifies the
choice-validation chain, ⊥ routing totality + kind, provenance address, replay
determinism, capability gating, corpus immutability, and procedure-leaf refusal.
"""

from __future__ import annotations

import hashlib
from itertools import pairwise
from pathlib import Path

from noise_chatbot.corpus import Corpus
from noise_chatbot.engine import Answer, Engine, ScriptedSelector, Session
from noise_chatbot.stores.gap import KIND_DEEP_BOTTOM, KIND_ROOT_BOTTOM, InMemoryGapStore
from tests.unit._engine_helpers import faq_corpus, load_nodes, node


def _assert_contiguous_path(corpus: Corpus, address: tuple[str, ...]) -> None:
    """Every address element must be a real child of its predecessor (a true descent path)."""
    assert address[0] == corpus.root_id
    for parent_id, child_id in pairwise(address):
        assert corpus.node(child_id).parent_id == parent_id, (
            f"address {address} fabricates edge {parent_id} -> {child_id}"
        )


def _engine(tmp_path: Path, script: list[str]) -> tuple[Engine, InMemoryGapStore]:
    corpus = faq_corpus(tmp_path)
    store = InMemoryGapStore()
    return Engine(corpus, ScriptedSelector(script), gap_store=store), store


# ── T2.3 — every answer carries its provenance address ─────────────────────────


def test_answer_carries_provenance_address(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path, ["topics", "about"])
    answer = engine.answer("what is trugs?")

    assert answer.is_bottom is False
    assert answer.text == "TRUGS is a constrained, executable subset of English."
    assert answer.address == ("root", "topics", "about")
    assert "root > topics > about" in answer.rendered()
    assert answer.gap is None
    assert store.gaps() == []  # a real answer writes no gap


# ── T2.2 — off-menu defense: validate → RETRY BOUNDED 1 → ⊥ ─────────────────────


def test_off_menu_return_retries_once_then_bottoms(tmp_path: Path) -> None:
    # both attempts illegal at the root menu → route to root_bottom
    engine, store = _engine(tmp_path, ["nonsense", "still-nonsense"])
    answer = engine.answer("???")

    assert answer.is_bottom is True
    assert answer.text == "No authored answer covers that yet."
    # exactly one retry — two attempts recorded at the single visited fork, both illegal
    assert len(answer.trace.steps) == 1
    assert [a.legal for a in answer.trace.steps[0].attempts] == [False, False]
    assert len(store.gaps()) == 1


def test_legal_choice_on_retry_is_accepted(tmp_path: Path) -> None:
    # first attempt off-menu, second legal → answer delivered, no ⊥
    engine, _ = _engine(tmp_path, ["oops", "topics", "about"])
    answer = engine.answer("what is trugs?")

    assert answer.is_bottom is False
    assert answer.address == ("root", "topics", "about")
    assert [a.legal for a in answer.trace.steps[0].attempts] == [False, True]


# ── T2.2b — ⊥ routing totality + kind discriminator (C4) ───────────────────────


def test_root_bottom_route_is_root_kind(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path, ["x", "x"])  # off-menu at root
    answer = engine.answer("q")
    assert answer.gap is not None
    assert answer.gap.kind == KIND_ROOT_BOTTOM
    assert answer.gap.death_node == "root"
    assert store.gaps()[0].kind == KIND_ROOT_BOTTOM


def test_deep_bottom_route_is_deep_kind(tmp_path: Path) -> None:
    # descend to topics, then fail there → nearest-ancestor bottom is deep_none (deep-⊥)
    engine, store = _engine(tmp_path, ["topics", "x", "x"])
    answer = engine.answer("q")
    assert answer.is_bottom is True
    assert answer.text == "No authored topic answer covers that."
    assert answer.gap is not None
    assert answer.gap.kind == KIND_DEEP_BOTTOM
    assert answer.gap.death_node == "topics"
    assert answer.address == ("root", "topics", "deep_none")
    assert store.gaps()[0].kind == KIND_DEEP_BOTTOM


def test_authored_bottom_selected_directly_writes_gap(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path, ["root_none"])  # user picks the ⊥ option itself
    answer = engine.answer("none of these")
    assert answer.is_bottom is True
    assert answer.gap is not None
    assert answer.gap.kind == KIND_ROOT_BOTTOM
    assert answer.gap.reason == "authored-bottom"
    assert len(store.gaps()) == 1


# ── T2.5 — trace completeness + replay determinism ─────────────────────────────


def test_replaying_recorded_choices_reproduces_answer(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    first = Engine(corpus, ScriptedSelector(["topics", "x", "about"])).answer("q")

    # replay the exact recorded attempt sequence over the same corpus
    replay = Engine(corpus, ScriptedSelector(first.trace.replay_choices())).answer("q")

    assert replay.text == first.text
    assert replay.address == first.address
    assert replay.is_bottom == first.is_bottom
    assert first.trace.trace_schema_version == "1"
    assert first.trace.corpus_schema_version == "1"


# ── T2.6 / SC-7 — capability gating (enumerator reads the session) ─────────────


def test_protected_child_excluded_for_anonymous_session(tmp_path: Path) -> None:
    # anonymous → "locked" is not on the menu, so selecting it is off-menu → ⊥
    engine, _ = _engine(tmp_path, ["topics", "locked", "locked"])
    answer = engine.answer("secret please")
    assert answer.is_bottom is True
    assert answer.text == "No authored topic answer covers that."


def test_protected_child_visible_with_capability(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    engine = Engine(corpus, ScriptedSelector(["topics", "locked"]))
    answer = engine.answer("secret please", session=Session(frozenset({"locked"})))
    assert answer.is_bottom is False
    assert answer.text == "classified"
    assert answer.address == ("root", "topics", "locked")


# ── T2.10 — procedure-leaf refusal (fail-honest ⊥, never execution) ────────────


def test_procedure_leaf_is_refused_not_executed(tmp_path: Path) -> None:
    engine, store = _engine(tmp_path, ["topics", "proc"])
    answer = engine.answer("run it")
    assert answer.is_bottom is True
    assert answer.gap is not None
    assert answer.gap.reason == "procedure-refused"
    # routed to the topics-level ⊥ (deep-⊥), delivering an authored no-answer — no execution
    assert answer.text == "No authored topic answer covers that."
    assert answer.gap.kind == KIND_DEEP_BOTTOM
    assert answer.gap.death_node == "proc"
    # provenance is the delivered ⊥'s true ancestry — NOT the death-node path + bottom
    assert answer.address == ("root", "topics", "deep_none")
    assert len(store.gaps()) == 1


# ── T2.9 — corpus immutability under engine operation (I7, the D8 IP line) ─────


def test_corpus_file_is_byte_identical_after_full_walk(tmp_path: Path) -> None:
    corpus_path = tmp_path / "faq.trug.json"
    faq_corpus(tmp_path)  # writes corpus_path
    before = hashlib.sha256(corpus_path.read_bytes()).hexdigest()

    # exercise every outcome: answer, root-⊥, deep-⊥, procedure-refusal
    corpus = faq_corpus(tmp_path)
    store = InMemoryGapStore()
    for script in (["topics", "about"], ["x", "x"], ["topics", "x", "x"], ["topics", "proc"]):
        result: Answer = Engine(corpus, ScriptedSelector(script), gap_store=store).answer("q")
        assert isinstance(result, Answer)

    after = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    assert after == before  # the engine never writes the corpus


# ── ⊥-routing provenance address is a true descent path (audit MEDIUM #1) ──────


def _climbing_corpus(tmp_path: Path, *, mid_bottom: bool) -> Corpus:
    """root → mid → leafbranch → only(answer); a root_bottom always, mid_bottom optional.

    Off-menu at leafbranch forces routing to climb past a bottom-less cursor.
    """
    nodes = [
        node("root", "branch", parent=None, contains=("mid", "rbottom")),
        node(
            "mid",
            "branch",
            parent="root",
            contains=("leafbranch", *(("mbottom",) if mid_bottom else ())),
            label="Mid",
        ),
        node("leafbranch", "branch", parent="mid", contains=("only",), label="Leaf branch"),
        node("only", "answer", parent="leafbranch", label="Only", answer="the only answer"),
        node("rbottom", "bottom", parent="root", label="None at all", answer="root floor"),
    ]
    if mid_bottom:
        nodes.append(node("mbottom", "bottom", parent="mid", label="None here", answer="mid floor"))
    return load_nodes(tmp_path, nodes, name=f"climb_{mid_bottom}.trug.json")


def test_routed_bottom_address_is_the_bottoms_true_ancestry(tmp_path: Path) -> None:
    # deep case: nearest bottom is mbottom (child of mid), death is leafbranch (its sibling's parent)
    corpus = _climbing_corpus(tmp_path, mid_bottom=True)
    answer = Engine(corpus, ScriptedSelector(["mid", "leafbranch", "x", "x"])).answer("q")
    assert answer.is_bottom is True
    assert answer.text == "mid floor"
    assert answer.gap is not None and answer.gap.death_node == "leafbranch"
    assert answer.address == ("root", "mid", "mbottom")  # NOT (...,'leafbranch','mbottom')
    _assert_contiguous_path(corpus, answer.address)


def test_routed_bottom_address_is_contiguous_when_falling_to_root(tmp_path: Path) -> None:
    # far case: no bottom until the root — address must not graft rbottom onto the death path
    corpus = _climbing_corpus(tmp_path, mid_bottom=False)
    answer = Engine(corpus, ScriptedSelector(["mid", "leafbranch", "x", "x"])).answer("q")
    assert answer.text == "root floor"
    assert answer.gap is not None and answer.gap.kind == KIND_ROOT_BOTTOM
    assert answer.address == ("root", "rbottom")
    _assert_contiguous_path(corpus, answer.address)


# ── protected ⊥ is never leaked via routing (audit MEDIUM #2) ──────────────────


def _protected_bottom_corpus(tmp_path: Path) -> Corpus:
    """topics has a PROTECTED bottom 'secret'; root has an unprotected floor 'rbottom'."""
    return load_nodes(
        tmp_path,
        [
            node("root", "branch", parent=None, contains=("topics", "rbottom")),
            node("topics", "branch", parent="root", contains=("a", "secret"), label="Topics"),
            node("a", "answer", parent="topics", label="A", answer="answer a"),
            node(
                "secret",
                "bottom",
                parent="topics",
                label="secret floor",
                answer="SECRET",
                protected=True,
            ),
            node("rbottom", "bottom", parent="root", label="None", answer="public floor"),
        ],
        name="protbottom.trug.json",
    )


def test_protected_bottom_not_leaked_to_anonymous_via_routing(tmp_path: Path) -> None:
    corpus = _protected_bottom_corpus(tmp_path)
    # anonymous off-menu at topics: 'secret' is protected → routing skips it, floors at rbottom
    answer = Engine(corpus, ScriptedSelector(["topics", "x", "x"])).answer("q")
    assert answer.text == "public floor"  # NOT "SECRET"
    assert answer.address == ("root", "rbottom")


def test_protected_bottom_reachable_with_capability_via_routing(tmp_path: Path) -> None:
    corpus = _protected_bottom_corpus(tmp_path)
    answer = Engine(corpus, ScriptedSelector(["topics", "x", "x"])).answer(
        "q", session=Session(frozenset({"secret"}))
    )
    assert answer.text == "SECRET"
    assert answer.gap is not None and answer.gap.kind == KIND_DEEP_BOTTOM
