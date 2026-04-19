"""JSON-file-backed store implementations (zero external deps beyond stdlib).

<trl>
MODULE json_file CONTAINS RECORD JsonFileResponseStore AND RECORD JsonFileBannedKeyStore
    AND RECORD JsonFileKnowledgeBaseStore.
EACH RECORD IMPLEMENTS PROCESS store.
</trl>

Read-only loaders (``JsonFileResponseStore``, ``JsonFileKnowledgeBaseStore``)
parse a TRUG-shaped JSON file at construction. ``JsonFileBannedKeyStore`` is
read/write: it loads existing bans at construction and persists every mutation
via an atomic ``tempfile`` + ``os.replace``.

Guardrails deliberately have no ``JsonFile*`` variant — guardrails ship
compiled-in + ``Server.with_guardrails(path)`` already merges custom JSON on
top, which is the established ergonomic (decided 2026-04-19).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from noise_chatbot.server.server import ResponseNode

_log = logging.getLogger("noise_chatbot.stores.json_file")


# AGENT jsonfileresponsestore SHALL IMPLEMENT PROCESS.
class JsonFileResponseStore:
    """Reads response nodes from a TRUG-shaped JSON file.

    <trl>
    RECORD JsonFileResponseStore CONTAINS RESOURCE path AND ARRAY nodes.
    FUNCTION responses SHALL READ DATA FROM RESOURCE path.
    </trl>

    Mirrors the extraction logic of ``Server.with_responses_from_trug``:
    every node whose ``properties.response`` or ``properties.description``
    is non-empty becomes a ``ResponseNode``. Missing file / malformed JSON
    is silently treated as an empty list (Go parity — logs a warning).
    """

    __slots__ = ("_nodes", "_path")

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._nodes: list[ResponseNode] = self._load()

    # FUNCTION responses SHALL RETURNS_TO SOURCE.
    def responses(self) -> list[ResponseNode]:
        return list(self._nodes)

    def _load(self) -> list[ResponseNode]:
        from noise_chatbot.server.server import ResponseNode

        try:
            data = self._path.read_bytes()
        except OSError as exc:
            _log.warning("could not load response TRUG %s: %s", self._path, exc)
            return []
        try:
            trug: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError as exc:
            _log.warning("could not parse response TRUG %s: %s", self._path, exc)
            return []

        nodes: list[ResponseNode] = []
        for node in trug.get("nodes", []):
            if not isinstance(node, dict):
                continue
            props = node.get("properties") or {}
            response = props.get("response") or props.get("description") or ""
            if not response:
                continue
            keywords = [k for k in props.get("keywords", []) if isinstance(k, str)]
            name = props.get("name", "")
            if isinstance(name, str) and name:
                keywords.append(name)
            nodes.append(ResponseNode(id=node.get("id", ""), keywords=keywords, response=response))
        return nodes


# AGENT jsonfilebannedkeystore SHALL IMPLEMENT PROCESS.
class JsonFileBannedKeyStore:
    """Ban store persisted to a JSON file with TTL-enforced expiry.

    <trl>
    RECORD JsonFileBannedKeyStore CONTAINS RESOURCE path AND OBJECT bans
        AND RECORD ttl.
    FUNCTION ban SHALL WRITE RECORD THEN WRITE DATA TO RESOURCE path.
    </trl>

    Persistence format: a JSON object mapping ``key_hex`` → ISO-8601
    datetime string. Atomic writes via ``tempfile`` + ``os.replace`` so a
    crash mid-write can't corrupt the file (R8 in LAB_1596).
    """

    __slots__ = ("_bans", "_lock", "_path", "ttl")

    def __init__(self, path: str | Path, ttl: timedelta = timedelta(hours=72)) -> None:
        self._path = Path(path)
        self.ttl: timedelta = ttl
        self._lock = threading.Lock()
        self._bans: dict[str, datetime] = self._load()

    def _load(self) -> dict[str, datetime]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            data: dict[str, str] = json.loads(raw)
        except json.JSONDecodeError as exc:
            _log.warning("could not parse ban file %s: %s", self._path, exc)
            return {}
        out: dict[str, datetime] = {}
        for k, v in data.items():
            try:
                out[k] = datetime.fromisoformat(v)
            except (TypeError, ValueError):
                continue
        return out

    def _persist_unlocked(self) -> None:
        """Write the current ban map to disk atomically. Caller must hold ``_lock``."""
        payload = {k: ts.isoformat() for k, ts in self._bans.items()}
        # Ensure parent dir exists.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: write to temp in same dir, then rename.
        fd, tmp_path = tempfile.mkstemp(
            prefix=self._path.name + ".",
            suffix=".tmp",
            dir=str(self._path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp_path, self._path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise

    # FUNCTION ban SHALL WRITE RECORD.
    def ban(self, key_hex: str, when: datetime | None = None) -> None:
        ts = when if when is not None else datetime.now()
        with self._lock:
            self._bans[key_hex] = ts
            self._persist_unlocked()

    # FUNCTION is_banned SHALL VALIDATE RECORD.
    def is_banned(self, key_hex: str, *, now: datetime | None = None) -> bool:
        current = now if now is not None else datetime.now()
        with self._lock:
            banned_at = self._bans.get(key_hex)
            if banned_at is None:
                return False
            if current - banned_at >= self.ttl:
                # Eager cleanup — pop and persist.
                self._bans.pop(key_hex, None)
                self._persist_unlocked()
                return False
            return True

    # FUNCTION unban SHALL REVOKE RECORD.
    def unban(self, key_hex: str) -> None:
        with self._lock:
            if key_hex in self._bans:
                self._bans.pop(key_hex, None)
                self._persist_unlocked()

    # FUNCTION active_bans SHALL RETURNS_TO SOURCE.
    def active_bans(self, *, now: datetime | None = None) -> Iterable[tuple[str, datetime]]:
        current = now if now is not None else datetime.now()
        with self._lock:
            return [(k, ts) for k, ts in self._bans.items() if current - ts < self.ttl]


# AGENT jsonfileknowledgebasestore SHALL IMPLEMENT PROCESS.
class JsonFileKnowledgeBaseStore:
    """Loads a TRUG knowledge base from a JSON file on construction.

    <trl>
    RECORD JsonFileKnowledgeBaseStore CONTAINS RESOURCE path AND OBJECT trug_data.
    FUNCTION context SHALL READ DATA FROM RESOURCE path.
    </trl>

    Silent on missing file / malformed JSON (matches ``Server.with_trug``).
    """

    __slots__ = ("_data",)

    def __init__(self, path: str | Path) -> None:
        self._data: dict[str, Any] | None = self._load(Path(path))

    @staticmethod
    def _load(path: Path) -> dict[str, Any] | None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            _log.warning("could not load knowledge base TRUG %s: %s", path, exc)
            return None
        try:
            loaded: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            _log.warning("could not parse knowledge base TRUG %s: %s", path, exc)
            return None
        if not isinstance(loaded, dict):
            return None
        return loaded

    # FUNCTION context SHALL RETURNS_TO SOURCE.
    def context(self) -> dict[str, object] | None:
        return self._data
