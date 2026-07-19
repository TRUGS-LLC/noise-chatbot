"""The constrained-selection port — one bounded instruction, one choice per fork.

<trl>
FUNCTION selector SHALL RECEIVE RECORD menu THEN RETURN SOLE RECORD choice.
</trl>

A backend returns exactly one node-id chosen from the presented menu — never free text.
The engine validates membership regardless of backend (B2), so engine safety does not
depend on any backend conforming. Backends implement this one ``Protocol``; the engine
imports nothing backend-specific.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class MenuOption:
    """One legal move at a fork: the node the choice descends to + its authored label."""

    node_id: str
    menu_label: str


#: The menu presented to a backend — the enumerator's session-gated legal-move list.
Menu = Sequence[MenuOption]


@runtime_checkable
class Selector(Protocol):
    """Chooses one option from a menu given the user's query.

    <trl>
    PROCESS Selector SHALL RECEIVE RECORD menu THEN RETURN SOLE RECORD choice.
    </trl>

    Returns the ``node_id`` of the chosen option. A conforming backend returns a member
    of ``menu``; a non-conforming one may not — the engine enforces membership either way.
    """

    def select(self, query: str, menu: Menu) -> str:
        """Return the chosen option's ``node_id``."""
        ...
