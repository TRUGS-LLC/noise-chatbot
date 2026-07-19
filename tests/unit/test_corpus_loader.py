"""SP1 loader tests — the corpus contract gate (T1.1 / T1.2 / T1.3).

Verifies (Phase 3):
- ``ASSERT FUNCTION loader SHALL_NOT LOAD ANY INVALID FILE corpus``
- ``ASSERT FUNCTION loader SHALL_NOT LOAD ANY FILE corpus WHEN INVALID RECORD role EXISTS``
- ``INVARIANT FUNCTION loader SHALL REQUIRE RECORD schema_version FROM EACH FILE corpus``
- the ``menu_label`` / ``root_bottom`` loader CONFIGURATION (C2 / C4)
- the ADR-001 ``trug`` CLI boundary: absent CLI and INVALID output both refuse cleanly.

The role-contract tests inject a pass-through validator so they exercise stage 2 in
isolation; the T1.3 tests drive the real published ``trug`` gate (skipped where the CLI
is not installed — CI installs it via the ``[engine]`` extra).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from noise_chatbot.corpus import (
    CorpusSchemaError,
    CorpusValidationError,
    load_corpus,
)
from noise_chatbot.corpus.validate import trug_validate


def _passthru(path: Path) -> None:
    """A validator that skips the ``trug`` gate — for hermetic role-contract tests."""


def _valid_corpus() -> dict[str, Any]:
    """A minimal ``trug``-VALID corpus: root branch + one answer + a root_bottom."""
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
                    "answer_text": "A constrained executable subset of English.",
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


def _write(tmp_path: Path, doc: dict[str, Any], name: str = "c.trug.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


# ── T1.2 — loader accepts a valid fixture and parses roles ─────────────────────


def test_loads_valid_corpus_and_parses_roles(tmp_path: Path) -> None:
    corpus = load_corpus(_write(tmp_path, _valid_corpus()), validator=_passthru)

    assert corpus.schema_version == "1"
    assert corpus.root_id == "root"
    assert corpus.root.role == "branch"
    assert corpus.root.menu_label is None  # the root is never a menu option

    about = corpus.node("about")
    assert about.role == "answer"
    assert about.menu_label == "What is TRUGS?"  # menu_label read on selectable nodes
    assert about.answer_text is not None and about.answer_text.startswith("A constrained")

    assert corpus.node("none").role == "bottom"
    assert [n.id for n in corpus.children("root")] == ["about", "none"]


def test_protected_marker_is_orthogonal_bool_not_a_role(tmp_path: Path) -> None:
    doc = _valid_corpus()
    doc["nodes"][0]["contains"].append("secret")
    doc["nodes"].append(
        {
            "id": "secret",
            "type": "CONCEPT",
            "parent_id": "root",
            "contains": [],
            "metric_level": "BASE_TOPIC",
            "dimension": "system",
            "properties": {
                "role": "answer",
                "menu_label": "Members-only detail",
                "answer_text": "classified",
                "protected": True,
            },
        }
    )
    corpus = load_corpus(_write(tmp_path, doc), validator=_passthru)

    secret = corpus.node("secret")
    assert secret.protected is True
    assert secret.role == "answer"  # protected did not displace the role
    assert corpus.node("about").protected is False


def test_procedure_role_is_accepted_at_load(tmp_path: Path) -> None:
    # procedure is schema-reserved: the loader accepts it (the executor refuses it, T2.10).
    doc = _valid_corpus()
    doc["nodes"][0]["contains"].append("proc")
    doc["nodes"].append(
        {
            "id": "proc",
            "type": "CONCEPT",
            "parent_id": "root",
            "contains": [],
            "metric_level": "BASE_TOPIC",
            "dimension": "system",
            "properties": {"role": "procedure", "menu_label": "Run the wizard"},
        }
    )
    corpus = load_corpus(_write(tmp_path, doc), validator=_passthru)
    assert corpus.node("proc").role == "procedure"


# ── T1.1 — loader refuses INVALID corpora (role contract, hermetic) ────────────


def _without_schema_version() -> dict[str, Any]:
    doc = _valid_corpus()
    del doc["nodes"][0]["properties"]["corpus_schema_version"]
    return doc


def _unknown_role() -> dict[str, Any]:
    doc = _valid_corpus()
    doc["nodes"][1]["properties"]["role"] = "mystery"
    return doc


def _missing_role() -> dict[str, Any]:
    doc = _valid_corpus()
    del doc["nodes"][1]["properties"]["role"]
    return doc


def _missing_menu_label() -> dict[str, Any]:
    doc = _valid_corpus()
    del doc["nodes"][1]["properties"]["menu_label"]
    return doc


def _no_root_bottom() -> dict[str, Any]:
    doc = _valid_corpus()
    # demote the only root-child bottom to an answer → no root_bottom remains
    doc["nodes"][2]["properties"]["role"] = "answer"
    return doc


def _protected_root_bottom() -> dict[str, Any]:
    doc = _valid_corpus()
    # the only root_bottom is protected → no session-accessible floor → refused (C4)
    doc["nodes"][2]["properties"]["protected"] = True
    return doc


def _parent_not_in_contains() -> dict[str, Any]:
    doc = _valid_corpus()
    # 'orphan' claims root as parent, but root.contains does not list it → disagreement
    doc["nodes"].append(
        {
            "id": "orphan",
            "type": "CONCEPT",
            "parent_id": "root",
            "contains": [],
            "metric_level": "BASE_TOPIC",
            "dimension": "system",
            "properties": {"role": "answer", "menu_label": "Orphan", "answer_text": "x"},
        }
    )
    return doc


def _contains_child_with_wrong_parent() -> dict[str, Any]:
    doc = _valid_corpus()
    doc["nodes"][0]["contains"].append("stray")  # root lists 'stray'...
    doc["nodes"].append(
        {
            "id": "stray",
            "type": "CONCEPT",
            "parent_id": "about",  # ...but 'stray' points at 'about', not root
            "contains": [],
            "metric_level": "BASE_TOPIC",
            "dimension": "system",
            "properties": {"role": "answer", "menu_label": "Stray", "answer_text": "x"},
        }
    )
    return doc


@pytest.mark.parametrize(
    ("name", "builder"),
    [
        ("no-schema-version", _without_schema_version),
        ("unknown-role", _unknown_role),
        ("missing-role", _missing_role),
        ("no-menu-label", _missing_menu_label),
        ("no-root-bottom", _no_root_bottom),
        ("protected-root-bottom", _protected_root_bottom),
        ("parent-not-in-contains", _parent_not_in_contains),
        ("contains-child-wrong-parent", _contains_child_with_wrong_parent),
    ],
)
def test_loader_refuses_invalid_corpus(
    tmp_path: Path, name: str, builder: Callable[[], dict[str, Any]]
) -> None:
    path = _write(tmp_path, builder(), name=f"{name}.trug.json")
    with pytest.raises(CorpusSchemaError):
        load_corpus(path, validator=_passthru)


# ── T1.3 — the ADR-001 `trug` CLI boundary ─────────────────────────────────────


def _absent_gate(path: Path) -> None:
    """Drive the real gate against a binary that does not exist → clean refusal."""
    trug_validate(path, binary="noise-chatbot-no-such-trug-xyz")


def test_gate_refuses_when_cli_absent(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_corpus())
    with pytest.raises(CorpusValidationError):
        load_corpus(path, validator=_absent_gate)


@pytest.mark.skipif(
    shutil.which("trug") is None,
    reason="requires the published trug CLI (pip install noise-chatbot[engine])",
)
def test_real_gate_refuses_trug_invalid_corpus(tmp_path: Path) -> None:
    # a broken envelope (missing required root fields) → `trug validate` INVALID
    path = _write(tmp_path, {"name": "x", "nodes": [{"id": "n"}]}, name="broken.trug.json")
    with pytest.raises(CorpusValidationError):
        load_corpus(path)  # default validator = the real published gate


@pytest.mark.skipif(
    shutil.which("trug") is None,
    reason="requires the published trug CLI (pip install noise-chatbot[engine])",
)
def test_real_gate_accepts_valid_corpus(tmp_path: Path) -> None:
    corpus = load_corpus(_write(tmp_path, _valid_corpus()))  # default real validator
    assert corpus.root_id == "root"
    assert corpus.node("about").role == "answer"
