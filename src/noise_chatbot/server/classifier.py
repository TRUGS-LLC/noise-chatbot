"""Response-node classifier types.

<trl>
MODULE server CONTAINS FUNCTION default_classifier AND RECORD Classifier.
FUNCTION Classifier SHALL MAP STRING user_text AS ARRAY node_ids.
FUNCTION Classifier SHALL_NOT WRITE ANY STRING text.
</trl>
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_chatbot.server.server import ResponseNode


# <trl>
# DEFINE Classifier AS FUNCTION 'that MAPS STRING user_text AND ARRAY nodes AS ARRAY ids.
# </trl>
Classifier = Callable[[str, list["ResponseNode"]], list[str]]
"""Picks matching ResponseNode IDs given user text.

Classifiers ONLY return IDs. They never generate response text — that's
the "LLM never composes" invariant.
"""


def default_classifier(user_text: str, nodes: list[ResponseNode]) -> list[str]:
    """Case-insensitive substring-match classifier.

    <trl>
    FUNCTION default_classifier SHALL MAP STRING user_text AS STRING lower
        THEN MAP EACH RECORD node AS INTEGER score BY FUNCTION count_keyword_matches
        THEN FILTER ARRAY nodes BY INTEGER score EXCEEDS 0
        THEN SORT RESULT BY INTEGER score
        THEN RETURNS_TO SOURCE ARRAY ids.
    </trl>

    Each keyword present in ``user_text`` (case-insensitive, as substring)
    adds 1 to that node's score. Nodes with score > 0 are returned, sorted
    by score descending. Score ties preserve input-list order.

    Go parity: ``server.go:defaultClassifier``.
    """
    lower = user_text.lower()
    scored: list[tuple[int, int, str]] = []
    for index, node in enumerate(nodes):
        score = sum(1 for kw in node.keywords if kw.lower() in lower)
        if score > 0:
            # Second element is input index for stable ordering on ties.
            scored.append((score, index, node.id))
    if not scored:
        return []
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [node_id for _, _, node_id in scored]
