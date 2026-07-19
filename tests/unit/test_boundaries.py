"""SP2 boundary test (T2.7 / SC-6) — the P4 extraction-clean transport isolation.

``INVARIANT SERVICE transport SHALL_NOT READ ANY DATA engine_code``: no module under
``noise/`` or ``protocol/`` may import ``engine``, ``corpus``, or ``select`` — absolute
(``noise_chatbot.engine``) or relative (``from ..engine``). Verified by an AST import
scan so later engine extraction stays cheap.
"""

from __future__ import annotations

import ast
from pathlib import Path

import noise_chatbot.noise as transport_noise
import noise_chatbot.protocol as transport_protocol

FORBIDDEN_SEGMENTS = frozenset({"engine", "corpus", "select"})


def _imported_modules(source: Path) -> set[str]:
    """Return every module referenced by an import in ``source``.

    Relative imports contribute their dotted tail (``from ..engine.select import x`` →
    ``engine.select``); absolute imports contribute the full name.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for statement in ast.walk(tree):
        if isinstance(statement, ast.Import):
            modules.update(alias.name for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom) and statement.module:
            modules.add(statement.module)
    return modules


def _references_engine_code(module: str) -> bool:
    segments = module.split(".")
    if segments and segments[0] in FORBIDDEN_SEGMENTS:  # relative tail, e.g. "engine.core"
        return True
    return module.startswith("noise_chatbot.") and any(s in FORBIDDEN_SEGMENTS for s in segments)


def test_transport_does_not_import_engine_corpus_or_select() -> None:
    roots = [
        Path(transport_noise.__file__).parent,
        Path(transport_protocol.__file__).parent,
    ]
    offenders: list[tuple[str, str]] = []
    for root in roots:
        for source in sorted(root.rglob("*.py")):
            for module in _imported_modules(source):
                if _references_engine_code(module):
                    offenders.append((source.name, module))

    assert offenders == [], f"transport modules import engine code (P4 breach): {offenders}"
