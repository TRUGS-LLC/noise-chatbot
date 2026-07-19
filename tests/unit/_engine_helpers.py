"""Shared corpus builders for the engine tests (not collected — leading underscore).

Builds ``trug``-shaped corpora and loads them through the real ``load_corpus`` with a
pass-through validator, so the tests exercise the engine over genuinely-parsed corpora
without depending on the ``trug`` CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from noise_chatbot.corpus import Corpus, load_corpus


def _passthru(path: Path) -> None:
    """Skip the ``trug`` gate — engine tests exercise parsed corpora, not the gate."""


def node(
    node_id: str,
    role: str,
    *,
    parent: str | None,
    contains: tuple[str, ...] = (),
    label: str | None = None,
    answer: str | None = None,
    protected: bool = False,
) -> dict[str, Any]:
    """Build one corpus node dict for the builders below."""
    props: dict[str, Any] = {"role": role}
    if parent is None:
        props["corpus_schema_version"] = "1"
    if label is not None:
        props["menu_label"] = label
    if answer is not None:
        props["answer_text"] = answer
    if protected:
        props["protected"] = True
    return {
        "id": node_id,
        "type": "CONCEPT",
        "parent_id": parent,
        "contains": list(contains),
        "metric_level": "BASE_TOPIC",
        "dimension": "system",
        "properties": props,
    }


def load_nodes(tmp_path: Path, nodes: list[dict[str, Any]], name: str = "c.trug.json") -> Corpus:
    """Wrap ``nodes`` in a TRUG envelope, write it, and load it (pass-through gate)."""
    doc = {
        "name": "t",
        "version": "1.0.0",
        "type": "PROJECT",
        "dimension": "system",
        "dimensions": {"system": {"description": "test"}},
        "nodes": nodes,
        "edges": [],
    }
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return load_corpus(path, validator=_passthru)


def faq_corpus(tmp_path: Path, *, name: str = "faq.trug.json") -> Corpus:
    """The canonical test tree exercising every walk outcome.

    root (branch)
      ├─ topics (branch)
      │    ├─ about       (answer)
      │    ├─ deep_none   (bottom)      → deep-⊥
      │    ├─ locked      (answer, protected)
      │    └─ proc        (procedure)   → refused
      └─ root_none (bottom)             → root_bottom / root-⊥
    """
    nodes = [
        node("root", "branch", parent=None, contains=("topics", "root_none")),
        node(
            "topics",
            "branch",
            parent="root",
            contains=("about", "deep_none", "locked", "proc"),
            label="Topics about TRUGS",
        ),
        node(
            "about",
            "answer",
            parent="topics",
            label="What is TRUGS?",
            answer="TRUGS is a constrained, executable subset of English.",
        ),
        node(
            "deep_none",
            "bottom",
            parent="topics",
            label="None of these topics",
            answer="No authored topic answer covers that.",
        ),
        node(
            "locked",
            "answer",
            parent="topics",
            label="Members-only detail",
            answer="classified",
            protected=True,
        ),
        node("proc", "procedure", parent="topics", label="Run the setup wizard"),
        node(
            "root_none",
            "bottom",
            parent="root",
            label="None of these",
            answer="No authored answer covers that yet.",
        ),
    ]
    return load_nodes(tmp_path, nodes, name=name)
