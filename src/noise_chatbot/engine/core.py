"""The generic TRUG interpreter — the graph is the program, the LLM is one instruction.

<trl>
PROCESS engine SHALL RECEIVE MESSAGE query THEN RETURN RECORD answer AND RECORD trace.
ASSERT PROCESS engine SHALL DERIVE EVERY RECORD behavior FROM FILE corpus.
ASSERT PROCESS engine SHALL VALIDATE EACH RECORD choice BY RECORD menu.
ASSERT PROCESS engine SHALL RETRY BOUNDED 1 ELSE RETURN RECORD bottom_route WHEN INVALID RECORD choice EXISTS.
ASSERT PROCESS engine SHALL RETURN RECORD bottom_route SUBJECT_TO RECORD nearest_ancestor.
ASSERT PROCESS engine SHALL APPEND RECORD address TO EACH RECORD answer.
ASSERT PROCESS engine SHALL WRITE RECORD gap TO FILE ledger WHEN RECORD bottom_route EXISTS.
INVARIANT PROCESS engine SHALL_NOT UPDATE ANY FILE corpus.
INVARIANT AGENT llm SHALL_NOT WRITE ANY RECORD answer.
ASSERT_NOT PROCESS engine SHALL EXECUTE ANY RECORD procedure_leaf.
</trl>

This module holds **zero domain knowledge**. Every behavior — which menus appear, which
answers deliver, where ⊥ routes — is read from the corpus; the only judgement is the
backend's single per-fork ``select``. There is no generation step between source and
delivery, so a wrong answer is possible but a *silent* one is not: a mis-selection is
self-locating (the trace), a miss routes to the authored ⊥ and writes a located gap, and
hallucination is structurally impossible. The engine never writes the corpus.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from noise_chatbot.corpus import (
    ROLE_ANSWER,
    ROLE_BOTTOM,
    ROLE_PROCEDURE,
    Corpus,
    CorpusNode,
)
from noise_chatbot.engine.legal_menu import legal_menu
from noise_chatbot.engine.select.port import Menu, MenuOption, Selector
from noise_chatbot.engine.session import Session
from noise_chatbot.engine.trace import TraceAttempt, TraceLog
from noise_chatbot.stores.gap import (
    KIND_DEEP_BOTTOM,
    KIND_ROOT_BOTTOM,
    GapRecord,
    GapStore,
)

Clock = Callable[[], datetime]


class EngineError(Exception):
    """Raised on a structural impossibility (e.g. a corpus that reached the engine
    without a reachable ⊥ — which the loader's ``root_bottom`` requirement prevents)."""


@dataclass(frozen=True, slots=True)
class Answer:
    """The delivered outcome: verbatim authored text + its provenance address.

    <trl>
    DEFINE RECORD answer CONTAINS STRING text AND ARRAY address AND RECORD trace.
    </trl>
    """

    text: str
    address: tuple[str, ...]
    is_bottom: bool
    gap: GapRecord | None
    trace: TraceLog

    def rendered(self) -> str:
        """The text as delivered, with a provenance line appended (for REPL / adapter)."""
        trail = " > ".join(self.address)
        return f"{self.text}\n\n[provenance: {trail}]"


def _default_clock() -> datetime:
    return datetime.now(tz=timezone.utc)


class Engine:
    """Executes a validated corpus as a program, one bounded ``select`` per fork.

    ``retry_bound`` realizes ``RETRY BOUNDED 1``: an off-menu return is retried once,
    then the walk routes to the nearest-ancestor ⊥ (B2 defense-in-depth). Safety does
    not depend on the backend conforming.
    """

    __slots__ = ("_clock", "_corpus", "_gap_store", "_retry_bound", "_selector")

    def __init__(
        self,
        corpus: Corpus,
        selector: Selector,
        *,
        gap_store: GapStore | None = None,
        retry_bound: int = 1,
        clock: Clock | None = None,
    ) -> None:
        self._corpus = corpus
        self._selector = selector
        self._gap_store = gap_store
        self._retry_bound = retry_bound
        self._clock = clock if clock is not None else _default_clock

    def answer(self, query: str, session: Session | None = None) -> Answer:
        """Walk the corpus for ``query`` and return the pre-authored leaf + trace.

        <trl>
        FUNCTION answer SHALL RECEIVE MESSAGE query THEN RETURN RECORD answer.
        </trl>
        """
        active = session if session is not None else Session.anonymous()
        # The trace is a self-contained, third-party-checkable record (SP-B): bind it to the
        # corpus content identity (SP-A) and record the session grant-set that gates every menu
        # (B5, sorted for a stable record). The terminal leaf is recorded at delivery (B4).
        trace = TraceLog(
            corpus_schema_version=self._corpus.schema_version,
            corpus_digest=self._corpus.corpus_digest,
            grants=tuple(sorted(active.capabilities)),
        )
        cursor = self._corpus.root
        path: list[str] = [cursor.id]

        while True:
            menu = self._enumerate(cursor.id, active)
            if not menu:
                return self._deliver_leaf(cursor, path, trace, query, active)
            chosen, attempts = self._select(query, menu)
            trace.visit(cursor.id, tuple(option.node_id for option in menu), attempts)
            if chosen is None:
                return self._route_bottom(cursor, path, trace, query, active, reason="off-menu")
            cursor = self._corpus.node(chosen)
            path.append(cursor.id)

    # ── enumeration (session-gated) ────────────────────────────────────────────

    def _enumerate(self, node_id: str, session: Session) -> list[MenuOption]:
        """Legal moves at ``node_id`` — delegates to the public ``legal_menu`` oracle.

        One source of truth (ADR-004, B6): the engine's gate and the checker's gate
        (``verify_trace``, SP-E) are the *same* function, so they cannot drift.
        """
        return legal_menu(self._corpus, node_id, session)

    # ── selection (validate → RETRY BOUNDED 1) ─────────────────────────────────

    def _select(self, query: str, menu: Menu) -> tuple[str | None, tuple[TraceAttempt, ...]]:
        legal = {option.node_id for option in menu}
        attempts: list[TraceAttempt] = []
        for _ in range(self._retry_bound + 1):
            choice = self._selector.select(query, menu)
            is_legal = choice in legal
            attempts.append(TraceAttempt(choice=choice, legal=is_legal))
            if is_legal:
                return choice, tuple(attempts)
        return None, tuple(attempts)

    # ── delivery ───────────────────────────────────────────────────────────────

    def _deliver_leaf(
        self, node: CorpusNode, path: list[str], trace: TraceLog, query: str, session: Session
    ) -> Answer:
        if node.role == ROLE_ANSWER:
            trace.terminate(node.id, is_bottom=False)  # B4 — the delivered leaf (id, not text)
            return Answer(
                text=self._answer_text(node),
                address=tuple(path),
                is_bottom=False,
                gap=None,
                trace=trace,
            )
        if node.role == ROLE_BOTTOM:
            # a bottom reached directly by selection — the fork above it missed. It was on
            # the menu, so it is session-accessible; its ancestry path is contiguous.
            return self._deliver_bottom(node, tuple(path), trace, query, reason="authored-bottom")
        if node.role == ROLE_PROCEDURE:
            # OUT-OF-SCOPE (V2): the executor refuses procedure leaves — fail-honest ⊥
            return self._route_bottom(node, path, trace, query, session, reason="procedure-refused")
        # a branch with no accessible children — no authored answer lives here
        return self._route_bottom(node, path, trace, query, session, reason="no-accessible-options")

    def _deliver_bottom(
        self, bottom: CorpusNode, path: tuple[str, ...], trace: TraceLog, query: str, *, reason: str
    ) -> Answer:
        kind = self._kind_of(bottom)
        death_node = bottom.parent_id if bottom.parent_id is not None else bottom.id
        gap = self._locate_gap(death_node, query, kind, reason)
        trace.terminate(bottom.id, is_bottom=True)  # B4 — delivered ⊥ leaf (address[-1])
        return Answer(
            text=self._answer_text(bottom),
            address=path,
            is_bottom=True,
            gap=gap,
            trace=trace,
        )

    def _route_bottom(
        self,
        from_node: CorpusNode,
        path: list[str],
        trace: TraceLog,
        query: str,
        session: Session,
        *,
        reason: str,
    ) -> Answer:
        bottom = self._nearest_bottom(from_node.id, session)
        # The provenance address is the delivered node's own root→node descent — a real
        # corpus path — not the death-node path with the bottom grafted on (which would
        # fabricate a parent→child edge when the ⊥ lives on an ancestor, not the cursor).
        gap = self._locate_gap(from_node.id, query, self._kind_of(bottom), reason)
        trace.terminate(bottom.id, is_bottom=True)  # B4 — routed-⊥ leaf, address[-1] == bottom.id
        return Answer(
            text=self._answer_text(bottom),
            address=self._path_to(bottom.id),
            is_bottom=True,
            gap=gap,
            trace=trace,
        )

    # ── ⊥ routing ──────────────────────────────────────────────────────────────

    def _nearest_bottom(self, node_id: str, session: Session) -> CorpusNode:
        """The nearest-ancestor bottom ``node_id`` can route to, honoring the session.

        Climbs from ``node_id`` to the root, returning the first bottom child the session
        may access — a protected ⊥ the session lacks is skipped, never leaked. Total by
        construction: the loader guarantees an **unprotected** ``root_bottom`` (C4), so an
        accessible floor always exists for every session.
        """
        current: str | None = node_id
        while current is not None:
            for child in self._corpus.children(current):
                if child.role == ROLE_BOTTOM and session.grants(child):
                    return child
            current = self._corpus.node(current).parent_id
        raise EngineError(  # pragma: no cover — the unprotected root_bottom requirement prevents this
            "no session-accessible bottom node — corpus lacks an unprotected root_bottom"
        )

    def _path_to(self, node_id: str) -> tuple[str, ...]:
        """The root→``node_id`` descent path (the node's ancestry, root first)."""
        chain: list[str] = []
        current: str | None = node_id
        while current is not None:
            chain.append(current)
            current = self._corpus.node(current).parent_id
        return tuple(reversed(chain))

    def _kind_of(self, bottom: CorpusNode) -> str:
        return KIND_ROOT_BOTTOM if bottom.parent_id == self._corpus.root_id else KIND_DEEP_BOTTOM

    # ── gap capture (located, never composing) ─────────────────────────────────

    def _locate_gap(self, death_node: str, query: str, kind: str, reason: str) -> GapRecord:
        gap = GapRecord(
            death_node=death_node,
            query=query,
            kind=kind,
            reason=reason,
            created_at=self._clock(),
        )
        if self._gap_store is not None:
            self._gap_store.record(gap)
        return gap

    def _answer_text(self, node: CorpusNode) -> str:
        if node.answer_text is None:  # pragma: no cover — loader requires it on answer/bottom
            raise EngineError(f"node {node.id!r} (role {node.role}) has no answer_text")
        return node.answer_text
