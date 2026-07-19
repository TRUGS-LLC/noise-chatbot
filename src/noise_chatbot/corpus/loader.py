"""Read-only corpus loader + parsed model.

<trl>
FUNCTION loader SHALL READ FILE corpus THEN VALIDATE ALL RECORD.
FUNCTION loader SHALL_NOT LOAD ANY INVALID FILE corpus.
FUNCTION loader SHALL_NOT LOAD ANY FILE corpus WHEN INVALID RECORD role EXISTS.
FUNCTION loader SHALL REQUIRE RECORD menu_label FROM EACH RECORD child.
FUNCTION loader SHALL REQUIRE RECORD root_bottom.
</trl>

Two stages, in order:
1. **The gate (ADR-001):** ``trug validate`` the file. A non-VALID file never reaches
   role parsing. Injectable (``validator=``) so engine unit tests stay hermetic; the
   default is the real published-CLI subprocess.
2. **The role contract:** parse ``docs/corpus_schema.md`` requirements — one root
   carrying ``corpus_schema_version``, every node role ∈ the vocabulary, every
   non-root node a ``menu_label``, and at least one ``root_bottom`` so the ⊥ retry
   chain is total (C4). Any violation refuses the load — the loader defines no writer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from noise_chatbot.corpus.errors import (
    CorpusError,
    CorpusSchemaError,
    CorpusValidationError,
)
from noise_chatbot.corpus.schema import (
    CORPUS_SCHEMA_VERSION,
    PROP_ANSWER_TEXT,
    PROP_CORPUS_SCHEMA_VERSION,
    PROP_MENU_LABEL,
    PROP_PROTECTED,
    PROP_ROLE,
    ROLE_ANSWER,
    ROLE_BOTTOM,
    VALID_ROLES,
    Role,
)
from noise_chatbot.corpus.validate import trug_validate

__all__ = [
    "Corpus",
    "CorpusError",
    "CorpusNode",
    "CorpusSchemaError",
    "CorpusValidationError",
    "Validator",
    "load_corpus",
]

Validator = Callable[[Path], None]


@dataclass(frozen=True, slots=True)
class CorpusNode:
    """One parsed corpus node — an immutable view over a validated TRUG node.

    <trl>
    DEFINE RECORD CorpusNode CONTAINS STRING id AND RECORD role AND ARRAY contains.
    </trl>
    """

    id: str
    role: Role
    parent_id: str | None
    contains: tuple[str, ...]
    menu_label: str | None
    answer_text: str | None
    protected: bool


@dataclass(frozen=True, slots=True)
class Corpus:
    """A parsed, validated corpus — the program the engine executes.

    <trl>
    DEFINE RECORD Corpus CONTAINS RECORD schema_version AND RECORD root AND ARRAY nodes.
    </trl>
    """

    schema_version: str
    root_id: str
    nodes: dict[str, CorpusNode]

    def node(self, node_id: str) -> CorpusNode:
        """Return the node with ``node_id`` (raises ``KeyError`` if unknown)."""
        return self.nodes[node_id]

    @property
    def root(self) -> CorpusNode:
        """Return the single root node."""
        return self.nodes[self.root_id]

    def children(self, node_id: str) -> list[CorpusNode]:
        """Return the ``contains`` children of ``node_id`` in authored order."""
        return [self.nodes[cid] for cid in self.nodes[node_id].contains]

    def parent(self, node_id: str) -> CorpusNode | None:
        """Return the parent node of ``node_id``, or ``None`` for the root."""
        parent_id = self.nodes[node_id].parent_id
        return self.nodes[parent_id] if parent_id is not None else None


def _mapping(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CorpusSchemaError(f"expected {what} to be an object, got {type(value).__name__}")
    return {str(k): v for k, v in value.items()}


def _parse_node(raw: object) -> CorpusNode:
    obj = _mapping(raw, "node")
    node_id = obj.get("id")
    if not isinstance(node_id, str) or not node_id:
        raise CorpusSchemaError(f"node missing a non-empty string 'id': {obj!r}")

    parent_raw = obj.get("parent_id")
    if parent_raw is not None and not isinstance(parent_raw, str):
        raise CorpusSchemaError(f"node {node_id!r} has a non-string 'parent_id'")
    parent_id: str | None = parent_raw

    contains_raw = obj.get("contains", [])
    if not isinstance(contains_raw, list) or not all(isinstance(c, str) for c in contains_raw):
        raise CorpusSchemaError(f"node {node_id!r} 'contains' must be a list of string ids")
    contains = tuple(str(c) for c in contains_raw)

    props = _mapping(obj.get("properties", {}), f"node {node_id!r} properties")

    role = props.get(PROP_ROLE)
    if role not in VALID_ROLES:
        raise CorpusSchemaError(
            f"node {node_id!r} has invalid role {role!r} — must be one of {sorted(VALID_ROLES)}"
        )

    is_root = parent_id is None
    label_raw = props.get(PROP_MENU_LABEL)
    if is_root and label_raw is not None:
        raise CorpusSchemaError(f"root node {node_id!r} must not carry a {PROP_MENU_LABEL!r}")
    if not is_root and (not isinstance(label_raw, str) or not label_raw):
        raise CorpusSchemaError(
            f"node {node_id!r} (non-root) requires a non-empty {PROP_MENU_LABEL!r}"
        )
    menu_label: str | None = label_raw if isinstance(label_raw, str) else None

    answer_raw = props.get(PROP_ANSWER_TEXT)
    if role in (ROLE_ANSWER, ROLE_BOTTOM) and (not isinstance(answer_raw, str) or not answer_raw):
        raise CorpusSchemaError(
            f"node {node_id!r} (role {role}) requires a non-empty {PROP_ANSWER_TEXT!r}"
        )
    answer_text: str | None = answer_raw if isinstance(answer_raw, str) else None

    protected = bool(props.get(PROP_PROTECTED, False))

    # The role literal is guaranteed by the VALID_ROLES membership check above.
    return CorpusNode(
        id=node_id,
        role=role,  # type: ignore[arg-type]
        parent_id=parent_id,
        contains=contains,
        menu_label=menu_label,
        answer_text=answer_text,
        protected=protected,
    )


def load_corpus(path: str | Path, *, validator: Validator = trug_validate) -> Corpus:
    """Validate then parse a corpus file, or refuse it.

    <trl>
    FUNCTION load_corpus SHALL READ FILE corpus THEN RETURN RECORD Corpus.
    </trl>

    ``validator`` is the ADR-001 gate seam — the default runs the published ``trug``
    CLI as a subprocess; tests inject a pass-through to exercise the role contract in
    isolation. Raises ``CorpusValidationError`` (gate) or ``CorpusSchemaError`` (role
    contract); both derive from ``CorpusError``.
    """
    corpus_path = Path(path)
    validator(corpus_path)  # stage 1 — the gate; refuses before any role parsing

    with corpus_path.open(encoding="utf-8") as handle:
        document = _mapping(json.load(handle), "corpus document")

    raw_nodes = document.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise CorpusSchemaError("corpus has no 'nodes' array")

    nodes: dict[str, CorpusNode] = {}
    for raw in raw_nodes:
        parsed = _parse_node(raw)
        if parsed.id in nodes:
            raise CorpusSchemaError(f"duplicate node id {parsed.id!r}")
        nodes[parsed.id] = parsed

    roots = [n for n in nodes.values() if n.parent_id is None]
    if len(roots) != 1:
        raise CorpusSchemaError(f"corpus must have exactly one root, found {len(roots)}")
    root = roots[0]

    # Referential integrity: every parent_id and every contained id must resolve.
    for node in nodes.values():
        if node.parent_id is not None and node.parent_id not in nodes:
            raise CorpusSchemaError(
                f"node {node.id!r} references unknown parent {node.parent_id!r}"
            )
        for child_id in node.contains:
            if child_id not in nodes:
                raise CorpusSchemaError(f"node {node.id!r} contains unknown child {child_id!r}")

    # schema_version — required, from the root, matching the pinned contract version.
    root_props = _root_properties(raw_nodes, root.id)
    version = root_props.get(PROP_CORPUS_SCHEMA_VERSION)
    if version is None:
        raise CorpusSchemaError(
            f"root node {root.id!r} missing required {PROP_CORPUS_SCHEMA_VERSION!r}"
        )
    if version != CORPUS_SCHEMA_VERSION:
        raise CorpusSchemaError(
            f"unsupported corpus_schema_version {version!r} "
            f"(this engine supports {CORPUS_SCHEMA_VERSION!r})"
        )

    # root_bottom — at least one bottom node is a direct child of the root (C4 totality).
    if not any(nodes[cid].role == ROLE_BOTTOM for cid in root.contains):
        raise CorpusSchemaError(
            f"corpus has no root_bottom — the root {root.id!r} needs at least one "
            f"direct child with role {ROLE_BOTTOM!r} so ⊥ routing is total"
        )

    return Corpus(schema_version=str(version), root_id=root.id, nodes=nodes)


def _root_properties(raw_nodes: list[object], root_id: str) -> dict[str, object]:
    for raw in raw_nodes:
        obj = _mapping(raw, "node")
        if obj.get("id") == root_id:
            return _mapping(obj.get("properties", {}), "root properties")
    raise CorpusSchemaError(f"root node {root_id!r} not found")  # pragma: no cover
