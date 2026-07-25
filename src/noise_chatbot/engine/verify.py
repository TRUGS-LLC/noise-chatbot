"""verify_trace — the executional-integrity checker (AAA #69 SP-E, the payoff, B8/C5).

<trl>
INTERFACE verify_trace SHALL RECEIVE RECORD corpus AND RECORD trace THEN RETURN RECORD verdict.
ASSERT FUNCTION verify_trace SHALL RE_DERIVE RECORD menu 'via legal_menu THEN VALIDATE recorded menu_ids EQUAL re_derived AND EACH RECORD choice IN re_derived.
ASSERT FUNCTION verify_trace SHALL REQUIRE RECORD contiguity.
ASSERT FUNCTION verify_trace SHALL BIND RECORD terminal_leaf 'EQUALS the walk endpoint.
ASSERT FUNCTION verify_trace SHALL MATCH RECORD corpus_digest 'else the walk is unbound.
ASSERT FUNCTION verify_trace SHALL VALIDATE RECORD membership 'only — SHALL_NOT PRODUCE ANY RECORD answer.
INVARIANT FUNCTION verify_trace SHALL_NOT INVOKE ANY RECORD selection_backend.
</trl>

Turns the executional-security property from a *claim* into a re-runnable *check* (C5): given a
corpus and a trace, is the trace a legal walk of the graph bearing this corpus's digest?

**Determinism stance (ADR-005, B7 / SP-D): this establishes legality of the recorded walk, NOT
model-reproducibility.** verify_trace replays the recorded choice_sequence against the DIGESTED
corpus via ``legal_menu`` — the *same* oracle the engine's gate delegates to — and **never
re-invokes any selection backend**, so its verdict is independent of the Anthropic backend's
sampling (no temperature/seed). It is a total, offline read: no network, no key, no weights.

**The digested corpus — not the trace — is the legality oracle.** verify_trace RE-DERIVES each
step's menu and rejects a trace whose self-reported ``menu_ids`` (attacker-supplied) disagree, so
a forged menu smuggling an off-corpus option cannot pass. It validates *membership* only and
produces no text — LLM-never-composes is structural here (there is no generation path).

**Scope (honest limits).** verify_trace validates walk *legality* — each choice a member of its
re-derived session-gated menu, contiguity, the terminal binding (RT-2), and the digest binding. It
does NOT validate engine *policy* the trace does not record: the retry bound (``RETRY BOUNDED 1``
is an ``Engine`` parameter, absent from the trace, so a walk with extra recorded retries still
reads as legal), nor the *authenticity* of the recorded grant-set (a forged grant-set re-derives a
wider menu — an access-control limit, so verify_trace is NOT an entitlement oracle). Both limits
are bounded to real, authored corpus nodes: a forgery can only ever surface an authored node the
digested corpus already contains — never an off-corpus id, never fabricated text.
"""

from __future__ import annotations

from dataclasses import dataclass

from noise_chatbot.corpus import ROLE_ANSWER, ROLE_BOTTOM, Corpus
from noise_chatbot.engine.legal_menu import legal_menu
from noise_chatbot.engine.session import Session
from noise_chatbot.engine.trace import TraceLog, TraceStep


@dataclass(frozen=True, slots=True)
class Verdict:
    """The checker's answer: was the trace a legal walk, and is it bound to *this* corpus?

    <trl>
    DEFINE RECORD verdict CONTAINS RECORD legal AND RECORD bound.
    </trl>

    ``legal`` — walk-legality under the recorded session (checkable for any trace, v1 or v2).
    ``bound`` — corpus-identity: the trace names the digest of *this* exact corpus; false for a
    digest-less / other-corpus trace, which is still checkable for legality but reports ``unbound``.
    """

    legal: bool
    bound: bool


def verify_trace(corpus: Corpus, trace: TraceLog) -> Verdict:
    """Re-derive the walk against the digested corpus and return ``{legal, bound}``."""
    session = Session(frozenset(trace.grants))
    return Verdict(
        legal=_is_legal_walk(corpus, trace, session),
        bound=_is_bound(corpus, trace),
    )


def _is_bound(corpus: Corpus, trace: TraceLog) -> bool:
    """True only when the trace names the digest of *this* exact corpus (SP-A identity)."""
    return trace.corpus_digest != "" and trace.corpus_digest == corpus.corpus_digest


def _is_legal_walk(corpus: Corpus, trace: TraceLog, session: Session) -> bool:
    # A legal walk records at least one choice — the recorded choice_sequence (replay ledger).
    # The root always presents a non-empty menu (the loader guarantees a root_bottom), so a
    # choiceless trace can never be a legal walk. Legality per fork is then re-derived below.
    if not trace.replay_choices():
        return False

    cursor = corpus.root_id
    for index, step in enumerate(trace.steps):
        # contiguity (part 1): the step is taken at the cursor the prior legal descent reached.
        if step.cursor_id != cursor:
            return False
        # RE-DERIVE the menu from the DIGESTED corpus — the oracle, NOT the trace's menu_ids.
        re_ids = tuple(option.node_id for option in legal_menu(corpus, cursor, session))
        # Well-formedness: a recorded step is a REAL fork — the engine visits only at a non-empty
        # menu (a leaf ends the walk without a visit) and its bounded selection always records at
        # least one attempt. An empty menu or zero attempts is structurally impossible from a real
        # walk; rejecting it closes the phantom-step / no-op-⊥ forgeries (SP-E adversarial sweep).
        if not re_ids or not step.attempts:
            return False
        # forged-menu rejection: the recorded menu_ids must equal the re-derived menu.
        if tuple(step.menu_ids) != re_ids:
            return False
        ok, accepted = _accepted_choice(step, re_ids)
        if not ok:
            return False  # the trace misreported an attempt's legality, or a legal one wasn't last
        if accepted is None:
            # every attempt was off-menu → this fork routes to ⊥; it must be the LAST step.
            if index != len(trace.steps) - 1:
                return False
            return _terminal_matches(
                trace, _nearest_bottom(corpus, cursor, session), is_bottom=True
            )
        # contiguity (part 2): descend to the accepted legal child.
        cursor = accepted

    # Every step descended legally. The walk ends where no legal move remains (a leaf); a
    # non-empty menu here means the trace stopped early (truncated) — illegal.
    if legal_menu(corpus, cursor, session):
        return False
    leaf_id, is_bottom = _resolve_leaf(corpus, cursor, session)
    return _terminal_matches(trace, leaf_id, is_bottom=is_bottom)


def _accepted_choice(step: TraceStep, re_ids: tuple[str, ...]) -> tuple[bool, str | None]:
    """The legal child this fork descends on (or None → ⊥ route). ``ok=False`` if the trace lies.

    Mirrors the engine's bounded selection: recorded legality must equal the truth re-derived
    from the corpus, and a legal choice ends the fork (so it must be the last attempt).
    """
    accepted: str | None = None
    for position, attempt in enumerate(step.attempts):
        really_legal = attempt.choice in re_ids
        if attempt.legal != really_legal:
            return False, None
        if really_legal:
            if position != len(step.attempts) - 1:
                return False, None
            accepted = attempt.choice
    return True, accepted


def _nearest_bottom(corpus: Corpus, node_id: str, session: Session) -> str | None:
    """The nearest-ancestor ⊥ ``node_id`` routes to, honoring the session — via ``legal_menu``.

    Climbs to the root, returning the first session-accessible ⊥ child. Uses the legality oracle
    (never the ungated children view), so a protected ⊥ the session lacks is skipped, not leaked.
    """
    current: str | None = node_id
    while current is not None:
        for option in legal_menu(corpus, current, session):
            if corpus.node(option.node_id).role == ROLE_BOTTOM:
                return option.node_id
        current = corpus.node(current).parent_id
    return None  # pragma: no cover — the unprotected root_bottom requirement guarantees a floor


def _resolve_leaf(corpus: Corpus, cursor: str, session: Session) -> tuple[str, bool]:
    """The delivered leaf a legal descent to ``cursor`` yields — mirrors the engine's delivery."""
    node = corpus.node(cursor)
    if node.role == ROLE_ANSWER:
        return cursor, False
    if node.role == ROLE_BOTTOM:
        return cursor, True
    # A procedure leaf (refused, ⊥) or a branch with no accessible children → route to ⊥.
    bottom = _nearest_bottom(corpus, cursor, session)
    if bottom is None:  # pragma: no cover — an accessible floor always exists (C4)
        return cursor, False
    return bottom, True


def _terminal_matches(trace: TraceLog, leaf_id: str | None, *, is_bottom: bool) -> bool:
    """RT-2: the recorded terminal must equal the endpoint the verified walk reaches.

    A bound trace MUST carry its terminal (so a digest-bearing walk cannot strip it to dodge the
    binding — the downgrade defense). A genuinely digest-less legacy trace may omit it, and then
    legality stands on the re-derived walk alone (B9).
    """
    terminal = trace.terminal
    if terminal is None:
        return trace.corpus_digest == ""
    if leaf_id is None:  # pragma: no cover
        return False
    return terminal.leaf_id == leaf_id and terminal.is_bottom is is_bottom
