"""Deterministic mock selection backends — CI-only, zero network / keys / weights.

<trl>
ASSERT PROCESS ci SHALL_NOT REQUIRE ANY RECORD model_weights.
</trl>

Two shapes:
- ``ScriptedSelector`` — replays a fixed sequence of node-ids (which may be off-menu, to
  exercise the B2 defense: validate → RETRY BOUNDED 1 → ⊥).
- ``KeywordSelector`` — picks the menu option whose label best matches the query by a
  deterministic substring score; used for the acid test and ordinary walks.
"""

from __future__ import annotations

from collections import deque

from noise_chatbot.engine.select.port import Menu


class ScriptedSelector:
    """Return queued node-ids in order — verbatim, even when off-menu.

    Raises ``IndexError`` when the script is exhausted, so a test that under-scripts a
    walk fails loudly rather than looping.
    """

    __slots__ = ("_queue",)

    def __init__(self, choices: list[str]) -> None:
        self._queue: deque[str] = deque(choices)

    def select(self, query: str, menu: Menu) -> str:
        if not self._queue:
            raise IndexError(
                "ScriptedSelector exhausted — walk requested more choices than scripted"
            )
        return self._queue.popleft()


class KeywordSelector:
    """Pick the option whose ``menu_label`` shares the most whitespace tokens with the query.

    Deterministic and offline. Ties break toward the earliest option (authored order),
    so behavior is a pure function of ``(query, menu)`` — no hidden state.
    """

    __slots__ = ()

    def select(self, query: str, menu: Menu) -> str:
        query_tokens = {tok for tok in query.lower().split() if tok}
        best_id = menu[0].node_id
        best_score = -1
        for option in menu:
            label_tokens = {tok for tok in option.menu_label.lower().split() if tok}
            score = len(query_tokens & label_tokens)
            if score > best_score:
                best_score = score
                best_id = option.node_id
        return best_id
