"""SP-E verify_trace tests (AAA #69, Phase-7 rows 23, 25-34): the executional-integrity checker.

Offline/hermetic — no network, no key, no selection backend: the checker replays the recorded
choices against the *digested* corpus. Covers the payoff round-trip, a committed golden v2
walk-trace fixture (regenerable from ``faq_corpus``), and the adversarial negatives — the
digested corpus, never the trace's self-reported ``menu_ids``, is the legality oracle.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from noise_chatbot.corpus import Corpus
from noise_chatbot.engine import (
    Engine,
    ScriptedSelector,
    Session,
    TraceAttempt,
    TraceLog,
    TraceStep,
    TraceTerminal,
    Verdict,
    verify_trace,
)
from tests.unit._engine_helpers import faq_corpus

FIXTURE = Path(__file__).parent / "golden_walk_trace.json"


def _to_dict(trace: TraceLog) -> dict[str, object]:
    """Serialize a v2 TraceLog to the golden-fixture JSON shape (single source with _from_dict)."""
    return {
        "corpus_schema_version": trace.corpus_schema_version,
        "trace_schema_version": trace.trace_schema_version,
        "corpus_digest": trace.corpus_digest,
        "grants": list(trace.grants),
        "terminal": None
        if trace.terminal is None
        else {"leaf_id": trace.terminal.leaf_id, "is_bottom": trace.terminal.is_bottom},
        "steps": [
            {
                "cursor_id": step.cursor_id,
                "menu_ids": list(step.menu_ids),
                "attempts": [{"choice": a.choice, "legal": a.legal} for a in step.attempts],
            }
            for step in trace.steps
        ],
    }


def _from_dict(doc: dict[str, Any]) -> TraceLog:
    terminal = (
        None
        if doc["terminal"] is None
        else TraceTerminal(
            leaf_id=doc["terminal"]["leaf_id"], is_bottom=doc["terminal"]["is_bottom"]
        )
    )
    steps = [
        TraceStep(
            cursor_id=step["cursor_id"],
            menu_ids=tuple(step["menu_ids"]),
            attempts=tuple(
                TraceAttempt(choice=a["choice"], legal=a["legal"]) for a in step["attempts"]
            ),
        )
        for step in doc["steps"]
    ]
    return TraceLog(
        corpus_schema_version=doc["corpus_schema_version"],
        trace_schema_version=doc["trace_schema_version"],
        steps=steps,
        corpus_digest=doc["corpus_digest"],
        grants=tuple(doc["grants"]),
        terminal=terminal,
    )


def _walk(
    tmp_path: Path, script: list[str], *, session: Session | None = None
) -> tuple[Corpus, TraceLog]:
    corpus = faq_corpus(tmp_path)
    ans = Engine(corpus, ScriptedSelector(script)).answer("q", session=session)
    return corpus, ans.trace


# ── the payoff round-trip (rows 26, 33 / SC-1, SC-5) ─────────────────────────────────
def test_verify_legal_walk_is_legal_and_bound(tmp_path: Path) -> None:
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    assert verify_trace(corpus, trace) == Verdict(legal=True, bound=True)


def test_bottom_route_verifies(tmp_path: Path) -> None:
    corpus, trace = _walk(tmp_path, ["topics", "x", "x"])  # off-menu twice → deep-⊥
    assert trace.terminal is not None and trace.terminal.is_bottom is True
    assert verify_trace(corpus, trace) == Verdict(legal=True, bound=True)


def test_procedure_leaf_routes_to_bottom_and_verifies(tmp_path: Path) -> None:
    corpus, trace = _walk(tmp_path, ["topics", "proc"])  # procedure refused → ⊥
    assert verify_trace(corpus, trace) == Verdict(legal=True, bound=True)


def test_protected_walk_with_capability_verifies(tmp_path: Path) -> None:
    corpus, trace = _walk(tmp_path, ["topics", "locked"], session=Session(frozenset({"locked"})))
    assert trace.grants == ("locked",)
    assert verify_trace(corpus, trace) == Verdict(legal=True, bound=True)


# ── committed golden fixture (row 33 / SC-5) ─────────────────────────────────────────
def test_committed_golden_fixture_verifies(tmp_path: Path) -> None:
    corpus = faq_corpus(tmp_path)
    trace = _from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert verify_trace(corpus, trace) == Verdict(legal=True, bound=True)


def test_golden_fixture_matches_regenerated(tmp_path: Path) -> None:
    # Regenerable from faq_corpus; a corpus/digest change breaks this loudly (discrimination).
    _corpus, trace = _walk(tmp_path, ["topics", "about"])
    assert _to_dict(trace) == json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── adversarial negatives: the digested corpus is the oracle, not the trace ──────────
def test_tampered_choice_is_illegal(tmp_path: Path) -> None:  # row 27
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    last = trace.steps[-1]
    forged = dataclasses.replace(
        trace,
        steps=[
            *trace.steps[:-1],
            dataclasses.replace(last, attempts=(TraceAttempt("ghost", legal=False),)),
        ],
    )
    assert verify_trace(corpus, forged).legal is False


def test_forged_menu_is_illegal(tmp_path: Path) -> None:  # row 27b — the folded HIGH
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    last = trace.steps[-1]
    # Smuggle an off-corpus option into menu_ids AND record a matching "legal" choice.
    forged = dataclasses.replace(
        trace,
        steps=[
            *trace.steps[:-1],
            dataclasses.replace(
                last,
                menu_ids=(*last.menu_ids, "ghost"),
                attempts=(TraceAttempt("ghost", legal=True),),
            ),
        ],
    )
    assert verify_trace(corpus, forged).legal is False


def test_forged_cursor_breaks_contiguity(tmp_path: Path) -> None:  # row 28
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    last = trace.steps[-1]
    forged = dataclasses.replace(
        trace, steps=[*trace.steps[:-1], dataclasses.replace(last, cursor_id="root")]
    )
    assert verify_trace(corpus, forged).legal is False


def test_forged_terminal_is_illegal(tmp_path: Path) -> None:  # row 28b — RT-2 terminal binding
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    assert trace.terminal is not None
    forged = dataclasses.replace(
        trace, terminal=dataclasses.replace(trace.terminal, leaf_id="root_none")
    )
    assert verify_trace(corpus, forged).legal is False


def test_bound_trace_stripped_of_terminal_is_illegal(tmp_path: Path) -> None:  # downgrade defense
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    assert verify_trace(corpus, dataclasses.replace(trace, terminal=None)).legal is False


def test_truncated_trace_is_illegal(tmp_path: Path) -> None:  # stops at a branch with legal moves
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    truncated = dataclasses.replace(trace, steps=trace.steps[:1], terminal=None)
    assert verify_trace(corpus, truncated).legal is False


def test_phantom_empty_step_at_leaf_is_illegal(tmp_path: Path) -> None:  # adversarial sweep
    # Append a structurally-impossible empty step at the answer leaf, then bind a sibling ⊥ as the
    # terminal — an attempt to launder an answered query into a false gap. Must be rejected.
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    forged = dataclasses.replace(
        trace,
        steps=[*trace.steps, TraceStep(cursor_id="about", menu_ids=(), attempts=())],
        terminal=TraceTerminal(leaf_id="deep_none", is_bottom=True),
    )
    assert verify_trace(corpus, forged).legal is False


def test_choiceless_trace_is_illegal(tmp_path: Path) -> None:  # a legal walk records >=1 choice
    corpus = faq_corpus(tmp_path)
    empty = TraceLog(corpus_schema_version="1", corpus_digest=corpus.corpus_digest)
    assert verify_trace(corpus, empty).legal is False


def test_zero_attempt_fork_is_illegal(tmp_path: Path) -> None:  # adversarial sweep
    # A step at a non-empty menu with ZERO attempts — a real fork always records >=1 selection.
    # verify must not read the vacuous no-op as a legitimate all-off-menu ⊥ route.
    corpus = faq_corpus(tmp_path)
    forged = TraceLog(
        corpus_schema_version="1",
        corpus_digest=corpus.corpus_digest,
        grants=(),
        steps=[TraceStep(cursor_id="root", menu_ids=("topics", "root_none"), attempts=())],
        terminal=TraceTerminal(leaf_id="root_none", is_bottom=True),
    )
    assert verify_trace(corpus, forged).legal is False


def test_digest_mismatch_is_unbound(tmp_path: Path) -> None:  # row 29
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    other = dataclasses.replace(trace, corpus_digest="tci1-sha256-" + "0" * 64)
    assert verify_trace(corpus, other) == Verdict(legal=True, bound=False)


def test_digestless_v1_is_legal_but_unbound(tmp_path: Path) -> None:  # row 32 — B9 additivity
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    v1 = dataclasses.replace(trace, corpus_digest="", terminal=None, trace_schema_version="1")
    assert verify_trace(corpus, v1) == Verdict(legal=True, bound=False)


# ── structural: {legal, bound} shape, membership-only, replay-only (rows 25, 30, 31) ─
def test_verdict_is_two_field_and_carries_no_text() -> None:
    verdict = Verdict(legal=True, bound=False)
    assert (verdict.legal, verdict.bound) == (True, False)
    assert not hasattr(verdict, "text")  # membership only — no answer path (LLM-never-composes)


def test_verify_is_offline_and_needs_no_backend(tmp_path: Path) -> None:
    # verify_trace's signature admits no selection backend; it runs purely on (corpus, trace).
    corpus, trace = _walk(tmp_path, ["topics", "about"])
    assert isinstance(verify_trace(corpus, trace), Verdict)
