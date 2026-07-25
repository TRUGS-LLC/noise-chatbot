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

**Wire provenance (AAA #69 SP-C, B3).** The walk's provenance — ``{corpus_digest, address}`` —
is carried **out-of-band**, so ``classify`` keeps its ``-> list[str]`` return and the
``Classifier`` ``Callable`` contract is never widened (the adapter deliberately drops
``answer.trace`` from the return). Each ``classify`` records its provenance in a **thread-local**
channel registered against the callable; the server reads it after the call via
:func:`provenance_of` (the adapter-identity check — it returns ``None`` for any classifier
without a channel, i.e. the default/fallback keyword classifiers). Thread-local storage means the
server's concurrent per-connection threads, which share one classifier, never see each other's
provenance — the race a naive shared attribute would suffer.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from noise_chatbot.engine.core import Engine
from noise_chatbot.engine.session import Session

if TYPE_CHECKING:
    from noise_chatbot.server.classifier import Classifier
    from noise_chatbot.server.server import ResponseNode

# Out-of-band provenance channels, keyed by the ``classify`` callable (SP-C). Each value is a
# ``threading.local`` so concurrent connection threads sharing one classifier are isolated. A
# WeakKeyDictionary drops the entry when the callable is collected — no leak, no global growth.
_PROVENANCE_CHANNELS: WeakKeyDictionary[object, threading.local] = WeakKeyDictionary()


def provenance_of(classifier: object) -> dict[str, Any] | None:
    """Return (and clear) the walk provenance of ``classifier``'s most recent call ON THIS THREAD.

    The adapter-identity check: any classifier without a registered channel — the default or
    fallback keyword classifiers — has no provenance, so this returns ``None`` for them. The
    engine adapter's channel is thread-local, so the returned provenance is exactly the walk this
    thread just performed, never another connection thread's.
    """
    channel = _PROVENANCE_CHANNELS.get(classifier)
    if channel is None:
        return None
    provenance: dict[str, Any] | None = getattr(channel, "provenance", None)
    channel.provenance = None
    return provenance


def as_classifier(engine: Engine, *, session: Session | None = None) -> Classifier:
    """Return a ``Classifier`` that walks ``engine`` and reports the delivered leaf id.

    The returned callable ignores the server's ``nodes`` list — the engine owns its own
    corpus — and returns ``[<leaf node id>]`` (or ``[]`` on an engine failure). The walk's
    provenance rides out-of-band; read it with :func:`provenance_of` (see the module docstring).
    """
    channel = threading.local()

    def classify(user_text: str, nodes: list[ResponseNode]) -> list[str]:
        channel.provenance = None  # reset per call — never carry a stale walk across requests
        try:
            answer = engine.answer(user_text, session)
        except Exception:
            # Fail-honest: never crash the serve loop, never silently degrade to the flat
            # classifier — return no match so the server delivers its honest no-answer.
            return []
        if not answer.address:
            return []
        channel.provenance = {
            "corpus_digest": answer.trace.corpus_digest,
            "address": list(answer.address),
        }
        return [answer.address[-1]]

    _PROVENANCE_CHANNELS[classify] = channel
    return classify
