"""The public, pure, session-gated legal-menu — the single legality oracle (ADR-004, B6).

<trl>
INTERFACE legal_menu SHALL RECEIVE RECORD corpus AND RECORD node AND RECORD session THEN RETURN RECORD menu.
ASSERT MODULE engine SHALL DECLARE FUNCTION legal_menu.
ASSERT FUNCTION _enumerate SHALL DELEGATE TO FUNCTION legal_menu.
</trl>

One source of truth for "what moves are legal at this node under this session". ``Engine._enumerate``
delegates here, and ``verify_trace`` (SP-E) re-derives the *exact* session-gated menu the walk saw
by calling this same function — so the engine's gate and the checker's gate can never drift.

It is deliberately module-level (not an ``Engine`` method) so the checker need not instantiate an
``Engine``. It is pure: a function of ``(corpus, node_id, session)`` with no I/O and no mutation.

The ungated ``Corpus.children`` (``loader.py``) is **not** the legality menu — it leaks protected
children the session lacks; a checker built on it would accept walks the engine would refuse.
"""

from __future__ import annotations

from noise_chatbot.corpus import Corpus
from noise_chatbot.engine.select.port import MenuOption
from noise_chatbot.engine.session import Session


def legal_menu(corpus: Corpus, node_id: str, session: Session) -> list[MenuOption]:
    """Legal moves at ``node_id`` — children, with protected ones the session lacks excluded."""
    return [
        MenuOption(node_id=child.id, menu_label=child.menu_label or child.id)
        for child in corpus.children(node_id)
        if session.grants(child)
    ]
