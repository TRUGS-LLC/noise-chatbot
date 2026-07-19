"""Corpus schema contract constants — the pinned role vocabulary (B4 / ADR-004).

<trl>
MODULE schema CONTAINS RECORD role AND RECORD schema_version.
FUNCTION loader SHALL REQUIRE RECORD schema_version FROM EACH FILE corpus.
FUNCTION loader SHALL REQUIRE RECORD role FROM EACH RECORD node.
</trl>

Canonical human copy of this contract ships as ``docs/corpus_schema.md`` (SP1
deliverable). The doc is authored from the same table; these constants are the
executable pin. Schema is **experimental until 1.0** — any change bumps
``CORPUS_SCHEMA_VERSION`` (ADR-004).
"""

from __future__ import annotations

from typing import Final, Literal

# The engine-level corpus schema version, carried at ``root.properties.corpus_schema_version``.
CORPUS_SCHEMA_VERSION: Final = "1"

# Node roles — an unknown/missing role is INVALID at load (the role gate, R1-F5).
ROLE_BRANCH: Final = "branch"
ROLE_ANSWER: Final = "answer"
ROLE_BOTTOM: Final = "bottom"
ROLE_PROCEDURE: Final = "procedure"

VALID_ROLES: Final = frozenset({ROLE_BRANCH, ROLE_ANSWER, ROLE_BOTTOM, ROLE_PROCEDURE})

Role = Literal["branch", "answer", "bottom", "procedure"]

# Property keys read off each node's ``properties`` object.
PROP_ROLE: Final = "role"
PROP_MENU_LABEL: Final = "menu_label"
PROP_ANSWER_TEXT: Final = "answer_text"
PROP_PROTECTED: Final = "protected"
PROP_CORPUS_SCHEMA_VERSION: Final = "corpus_schema_version"
