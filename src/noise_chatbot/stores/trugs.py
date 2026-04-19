"""``trugs-store``-backed store adapters (requires the ``[trugs]`` optional extra).

<trl>
MODULE trugs CONTAINS RECORD TrugsGuardrailStore AND RECORD TrugsResponseStore
    AND RECORD TrugsBannedKeyStore AND RECORD TrugsKnowledgeBaseStore.
EACH RECORD DEPENDS_ON MODULE trugs_store.
</trl>

Import requires ``pip install noise-chatbot[trugs]``. Without the extra
installed, importing this module raises ``ImportError`` with the install
hint at the top of the traceback — callers should not catch it; they should
install the extra.

Every adapter works by pointing at an ``InMemoryGraphStore`` instance:

- Read-only loaders (``TrugsGuardrailStore``, ``TrugsResponseStore``,
  ``TrugsKnowledgeBaseStore``) project graph nodes into the shape the
  Server's internal logic expects (``ResponseNode`` for guardrails/responses,
  raw dict for KB).
- ``TrugsBannedKeyStore`` mutates the graph in place. Persistence of the
  graph itself is the caller's responsibility — e.g. wrap the graph in
  ``trugs_store.JsonFilePersistence`` or ``PostgresPersistence`` and
  flush before/after the server runs.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from trugs_store import (
        InMemoryGraphStore,
        JsonFilePersistence,
        read_trug,
    )
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "noise_chatbot.stores.trugs requires the [trugs] extra. "
        "Install with: pip install noise-chatbot[trugs]"
    ) from exc

if TYPE_CHECKING:
    from noise_chatbot.server.server import ResponseNode


_DEFAULT_GUARDRAIL_TYPE = "GUARDRAIL"
_DEFAULT_RESPONSE_TYPE = "RESPONSE"
_BAN_NODE_TYPE = "BAN"


def _load_graph(source: InMemoryGraphStore | str | Path) -> InMemoryGraphStore:
    """Normalize a source into an ``InMemoryGraphStore``.

    Accepts an existing store, a ``str`` path, or a ``Path`` — loads via
    ``JsonFilePersistence().load`` for the latter two.
    """
    if isinstance(source, InMemoryGraphStore):
        return source
    return JsonFilePersistence().load(str(source))


def _response_node_from_graph_node(node: dict[str, Any]) -> ResponseNode | None:
    """Project a graph node into a ``ResponseNode`` if it has a response; else ``None``."""
    from noise_chatbot.server.server import ResponseNode

    props = node.get("properties") or {}
    response = props.get("response") or props.get("description") or ""
    if not response:
        return None
    keywords = [k for k in props.get("keywords", []) if isinstance(k, str)]
    name = props.get("name", "")
    if isinstance(name, str) and name and name not in keywords:
        keywords.append(name)
    return ResponseNode(id=node.get("id", ""), keywords=keywords, response=response)


# AGENT trugsguardrailstore SHALL IMPLEMENT PROCESS.
class TrugsGuardrailStore:
    """``GuardrailStore`` backed by a ``trugs-store`` graph.

    <trl>
    RECORD TrugsGuardrailStore CONTAINS RECORD graph AND STRING node_type.
    FUNCTION guardrails SHALL READ DATA FROM RECORD graph.
    </trl>
    """

    __slots__ = ("_graph", "_node_type")

    def __init__(
        self,
        source: InMemoryGraphStore | str | Path,
        node_type: str = _DEFAULT_GUARDRAIL_TYPE,
    ) -> None:
        self._graph: InMemoryGraphStore = _load_graph(source)
        self._node_type = node_type

    # FUNCTION guardrails SHALL RETURNS_TO SOURCE.
    def guardrails(self) -> list[ResponseNode]:
        nodes: list[ResponseNode] = []
        for graph_node in self._graph.find_nodes(type=self._node_type):
            converted = _response_node_from_graph_node(graph_node)
            if converted is not None:
                nodes.append(converted)
        return nodes


# AGENT trugsresponsestore SHALL IMPLEMENT PROCESS.
class TrugsResponseStore:
    """``ResponseStore`` backed by a ``trugs-store`` graph.

    <trl>
    RECORD TrugsResponseStore CONTAINS RECORD graph AND STRING node_type.
    FUNCTION responses SHALL READ DATA FROM RECORD graph.
    </trl>
    """

    __slots__ = ("_graph", "_node_type")

    def __init__(
        self,
        source: InMemoryGraphStore | str | Path,
        node_type: str = _DEFAULT_RESPONSE_TYPE,
    ) -> None:
        self._graph: InMemoryGraphStore = _load_graph(source)
        self._node_type = node_type

    # FUNCTION responses SHALL RETURNS_TO SOURCE.
    def responses(self) -> list[ResponseNode]:
        nodes: list[ResponseNode] = []
        for graph_node in self._graph.find_nodes(type=self._node_type):
            converted = _response_node_from_graph_node(graph_node)
            if converted is not None:
                nodes.append(converted)
        return nodes


# AGENT trugsbannedkeystore SHALL IMPLEMENT PROCESS.
class TrugsBannedKeyStore:
    """``BannedKeyStore`` persisted as ``BAN`` nodes in a ``trugs-store`` graph.

    <trl>
    RECORD TrugsBannedKeyStore CONTAINS RECORD graph AND RECORD ttl.
    FUNCTION ban SHALL WRITE RECORD ban_node TO RECORD graph.
    </trl>

    The graph is mutated in place. Persistence of the graph itself is the
    caller's responsibility (flush via ``JsonFilePersistence.save()`` or the
    postgres backend). This keeps the store layer storage-backend-agnostic.
    """

    __slots__ = ("_graph", "_lock", "ttl")

    def __init__(
        self,
        source: InMemoryGraphStore | str | Path,
        ttl: timedelta = timedelta(hours=72),
    ) -> None:
        self._graph: InMemoryGraphStore = _load_graph(source)
        self.ttl: timedelta = ttl
        self._lock = threading.Lock()

    def _ban_timestamp(self, key_hex: str) -> datetime | None:
        node = self._graph.get_node(key_hex)
        if node is None:
            return None
        if node.get("type") != _BAN_NODE_TYPE:
            return None
        raw = (node.get("properties") or {}).get("banned_at")
        if not isinstance(raw, str):
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    # FUNCTION ban SHALL WRITE RECORD.
    def ban(self, key_hex: str, when: datetime | None = None) -> None:
        ts = when if when is not None else datetime.now()
        with self._lock:
            # Remove any existing ban node so properties update cleanly.
            if self._graph.get_node(key_hex) is not None:
                self._graph.delete_node(key_hex)
            self._graph.add_node(
                {
                    "id": key_hex,
                    "type": _BAN_NODE_TYPE,
                    "parent_id": None,
                    "contains": [],
                    "properties": {"banned_at": ts.isoformat()},
                    "metric_level": "BASE_BAN",
                    "dimension": "ban_tracking",
                }
            )

    # FUNCTION is_banned SHALL VALIDATE RECORD.
    def is_banned(self, key_hex: str, *, now: datetime | None = None) -> bool:
        current = now if now is not None else datetime.now()
        with self._lock:
            ts = self._ban_timestamp(key_hex)
            if ts is None:
                return False
            if current - ts >= self.ttl:
                # Eager cleanup.
                self._graph.delete_node(key_hex)
                return False
            return True

    # FUNCTION unban SHALL REVOKE RECORD.
    def unban(self, key_hex: str) -> None:
        with self._lock:
            if self._graph.get_node(key_hex) is not None:
                self._graph.delete_node(key_hex)

    # FUNCTION active_bans SHALL RETURNS_TO SOURCE.
    def active_bans(self, *, now: datetime | None = None) -> Iterable[tuple[str, datetime]]:
        current = now if now is not None else datetime.now()
        out: list[tuple[str, datetime]] = []
        with self._lock:
            for node in self._graph.find_nodes(type=_BAN_NODE_TYPE):
                raw = (node.get("properties") or {}).get("banned_at")
                if not isinstance(raw, str):
                    continue
                try:
                    ts = datetime.fromisoformat(raw)
                except ValueError:
                    continue
                if current - ts < self.ttl:
                    out.append((node.get("id", ""), ts))
        return out


# AGENT trugsknowledgebasestore SHALL IMPLEMENT PROCESS.
class TrugsKnowledgeBaseStore:
    """``KnowledgeBaseStore`` backed by a TRUG file read through ``trugs_store``.

    <trl>
    RECORD TrugsKnowledgeBaseStore CONTAINS OBJECT trug_payload.
    FUNCTION context SHALL RETURNS_TO SOURCE OBJECT trug_payload.
    </trl>

    Uses ``trugs_store.read_trug`` — honors the ``PORT_DSN`` env var to read
    from a PostgreSQL TRUG database, else reads from the JSON path.
    """

    __slots__ = ("_data",)

    def __init__(self, source: str | Path | dict[str, Any]) -> None:
        if isinstance(source, dict):
            self._data: dict[str, Any] | None = source
            return
        try:
            self._data = read_trug(source)
        except (FileNotFoundError, RuntimeError):
            self._data = None

    # FUNCTION context SHALL RETURNS_TO SOURCE.
    def context(self) -> dict[str, object] | None:
        return self._data
