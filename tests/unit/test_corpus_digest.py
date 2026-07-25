"""SP-A corpus content-identity tests (AAA #69, Phase-7 rows 1-6 + 3b).

Verifies (Phase 3):
- ``ASSERT PROCESS load_corpus SHALL DERIVE RECORD corpus_digest FROM the parsed corpus
  document via trugs_tools.digest.digest (artifact_identity, L1), before it returns the Corpus``
- ``ASSERT RECORD corpus_digest SHALL EQUALS RECORD tci_digest`` (the ``tci1-sha256-…`` shape)
- the ADR-001 choice of ``digest``/artifact_identity (L1) over the flat, order-sensitive
  ``content_address``: two content-identical corpora — **including a node-reordered one** —
  hash equal, while a corpus differing only in ``answer_text`` hashes differently.

Offline/hermetic: the corpora load through the real ``load_corpus`` with a pass-through
validator (the ``trug`` gate is exercised elsewhere, ``test_corpus_loader.py``).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from trugs_tools import digest as _tci
from trugs_tools.digest import digest as content_digest

from noise_chatbot.corpus import Corpus, load_corpus


def _passthru(_path: Path) -> None:
    """Skip the ``trug`` gate — these tests exercise the parsed-document digest, not the gate."""


def _doc(*, about_answer: str = "A constrained executable subset of English.") -> dict[str, Any]:
    """A minimal ``trug``-VALID corpus document: root branch + one answer + a root_bottom."""
    return {
        "name": "faq",
        "version": "1.0.0",
        "type": "PROJECT",
        "dimension": "system",
        "dimensions": {"system": {"description": "demo"}},
        "nodes": [
            {
                "id": "root",
                "type": "CONCEPT",
                "parent_id": None,
                "contains": ["about", "none"],
                "metric_level": "BASE_TOPIC",
                "dimension": "system",
                "properties": {"role": "branch", "corpus_schema_version": "1"},
            },
            {
                "id": "about",
                "type": "CONCEPT",
                "parent_id": "root",
                "contains": [],
                "metric_level": "BASE_TOPIC",
                "dimension": "system",
                "properties": {
                    "role": "answer",
                    "menu_label": "What is TRUGS?",
                    "answer_text": about_answer,
                },
            },
            {
                "id": "none",
                "type": "CONCEPT",
                "parent_id": "root",
                "contains": [],
                "metric_level": "BASE_TOPIC",
                "dimension": "system",
                "properties": {
                    "role": "bottom",
                    "menu_label": "None of these",
                    "answer_text": "No authored answer covers that yet.",
                },
            },
        ],
        "edges": [],
    }


def _load(tmp_path: Path, doc: dict[str, Any], name: str = "c.trug.json") -> Corpus:
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return load_corpus(path, validator=_passthru)


# ── Row 1 / SC-6: derived at load from the parsed document via digest() ──────────────
def test_corpus_digest_equals_content_digest_of_document(tmp_path: Path) -> None:
    doc = _doc()
    corpus = _load(tmp_path, doc)
    assert corpus.corpus_digest == content_digest(doc)


# ── Row 2 / SC-7: the tci1-sha256 artifact_identity shape ────────────────────────────
def test_corpus_digest_shape(tmp_path: Path) -> None:
    corpus = _load(tmp_path, _doc())
    prefix = f"{_tci.TCI_VERSION}-{_tci.TCI_ALGO}-"
    assert prefix == "tci1-sha256-"
    assert corpus.corpus_digest.startswith(prefix)
    hexpart = corpus.corpus_digest[len(prefix) :]
    assert len(hexpart) == 64 and all(c in "0123456789abcdef" for c in hexpart)


# ── Row 3: order-INVARIANT (artifact_identity L1) — the SP-1 fix's whole point ────────
def test_corpus_digest_order_invariant(tmp_path: Path) -> None:
    doc = _doc()
    reordered = dict(doc)
    reordered["nodes"] = list(reversed(doc["nodes"]))  # same content, different node order
    a = _load(tmp_path, doc, name="a.trug.json")
    b = _load(tmp_path, reordered, name="b.trug.json")
    assert a.corpus_digest == b.corpus_digest


# ── Row 3: canonical (RFC-8785), not raw-bytes — key-order / whitespace insensitive ──
def test_corpus_digest_canonical_not_raw_bytes(tmp_path: Path) -> None:
    doc = _doc()
    # Byte-different source: reordered top-level keys + pretty-printed whitespace.
    rekeyed = {"edges": doc["edges"], "nodes": doc["nodes"], **doc}
    p1 = tmp_path / "compact.trug.json"
    p2 = tmp_path / "pretty.trug.json"
    p1.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    p2.write_text(json.dumps(rekeyed, indent=4), encoding="utf-8")
    assert p1.read_bytes() != p2.read_bytes()  # genuinely byte-different sources
    c1 = load_corpus(p1, validator=_passthru)
    c2 = load_corpus(p2, validator=_passthru)
    assert c1.corpus_digest == c2.corpus_digest


# ── Row 4: compute-once / re-load stability ──────────────────────────────────────────
def test_corpus_digest_stable_on_reload(tmp_path: Path) -> None:
    doc = _doc()
    path = tmp_path / "c.trug.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    first = load_corpus(path, validator=_passthru)
    second = load_corpus(path, validator=_passthru)
    assert first.corpus_digest == second.corpus_digest != ""


# ── Row 3b: corpus_digest DISCRIMINATES — bound=true means "this exact corpus" ────────
def test_corpus_digest_discriminates_on_answer_text(tmp_path: Path) -> None:
    a = _load(tmp_path, _doc(about_answer="A."), name="a.trug.json")
    b = _load(tmp_path, _doc(about_answer="Something else entirely."), name="b.trug.json")
    assert a.corpus_digest != b.corpus_digest


# ── Row 6: hand-built Corpus stays valid without the argument (additive default) ──────
def test_hand_built_corpus_defaults_empty_digest() -> None:
    corpus = Corpus(schema_version="1", root_id="root", nodes={})
    assert corpus.corpus_digest == ""


# ── INVARIANT engine SHALL_NOT UPDATE corpus — frozen; digest set once, never mutated ─
def test_corpus_digest_is_frozen(tmp_path: Path) -> None:
    corpus = _load(tmp_path, _doc())
    with pytest.raises(dataclasses.FrozenInstanceError):
        corpus.corpus_digest = "tci1-sha256-tampered"  # type: ignore[misc]


# ── Row 5 / config: both trugs-tools pins bumped to the digest-shipping release ───────
def test_both_pyproject_pins_are_2_1_1() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert "trugs-tools==2.1.0" not in text
    assert text.count("trugs-tools==2.1.1") >= 2
