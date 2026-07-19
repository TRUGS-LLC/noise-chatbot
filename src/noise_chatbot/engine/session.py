"""Session capability object — threaded through the enumerator from day one (D6/P3).

<trl>
INVARIANT PROCESS enumerator SHALL READ RECORD session.
ASSERT PROCESS enumerator SHALL EXCLUDE EACH PROTECTED RECORD child FROM RECORD menu.
</trl>

V1 sessions are anonymous (no capabilities), so protected subtrees are always excluded.
The object exists now — even empty — so V2's capability doors are a data change, not an
architecture change (the forward-compat commitment from the design of record).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from noise_chatbot.corpus import CorpusNode


@dataclass(frozen=True, slots=True)
class Session:
    """An immutable set of capabilities a caller holds.

    A capability is keyed by the node id it unlocks. V2 will mint richer capability
    grammars; V1 needs only "does this session unlock this protected node".
    """

    capabilities: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def anonymous(cls) -> Session:
        """The default V1 session — grants nothing, so every protected node is excluded."""
        return cls()

    def grants(self, node: CorpusNode) -> bool:
        """Return whether this session may see ``node`` when it is ``protected``.

        A non-protected node is always visible; a protected node is visible only when
        the session holds a capability keyed by the node's id.
        """
        if not node.protected:
            return True
        return node.id in self.capabilities
