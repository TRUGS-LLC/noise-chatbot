"""Server adapter — expose the engine at the ``with_classifier`` seam (D9 / ADR-005).

<trl>
FUNCTION adapter SHALL IMPLEMENT FUNCTION classifier.
INVARIANT PROCESS reporter SHALL_NOT WRITE ANY RECORD answer.
</trl>

``as_classifier`` wraps an :class:`Engine` as a ``Classifier`` — the seam a Noise server
plugs in via ``Server.with_classifier(...)`` for the served demo. It conforms to the
contract exactly: it returns **node ids, never composed text** (the delivered leaf's id),
so the server owns delivery of the pre-authored answer.

**Fail-honest (ADR-005):** an engine exception yields an honest non-answer (an empty id
list → the server's no-match reply), never a crash of the serve loop and never a silent
fallback to a flat keyword classifier. Degradation to the flat classifier remains an
explicit operator choice (``Server.with_fallback_classifier``), visible and opt-in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from noise_chatbot.engine.core import Engine
from noise_chatbot.engine.session import Session

if TYPE_CHECKING:
    from noise_chatbot.server.classifier import Classifier
    from noise_chatbot.server.server import ResponseNode


def as_classifier(engine: Engine, *, session: Session | None = None) -> Classifier:
    """Return a ``Classifier`` that walks ``engine`` and reports the delivered leaf id.

    The returned callable ignores the server's ``nodes`` list — the engine owns its own
    corpus — and returns ``[<leaf node id>]`` (or ``[]`` on an engine failure).
    """

    def classify(user_text: str, nodes: list[ResponseNode]) -> list[str]:
        try:
            answer = engine.answer(user_text, session)
        except Exception:
            # Fail-honest: never crash the serve loop, never silently degrade to the flat
            # classifier — return no match so the server delivers its honest no-answer.
            return []
        return [answer.address[-1]] if answer.address else []

    return classify
