"""SP2 acid test (T2.1) — every behavior derives from the corpus, none from engine code.

``ASSERT PROCESS engine SHALL DERIVE EVERY RECORD behavior FROM FILE corpus`` (D7). The
test hashes every engine source file, drives two different corpora through the *same*
engine class with the *same* script, and asserts the answers differ while the engine
source is byte-identical — behavior changed with zero engine-code change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import noise_chatbot.engine as engine_pkg
from noise_chatbot.corpus import Corpus
from noise_chatbot.engine import Engine, ScriptedSelector
from tests.unit._engine_helpers import load_nodes, node


def _engine_source_hashes() -> dict[str, str]:
    engine_dir = Path(engine_pkg.__file__).parent
    return {
        str(py.relative_to(engine_dir)): hashlib.sha256(py.read_bytes()).hexdigest()
        for py in sorted(engine_dir.rglob("*.py"))
    }


def _single_answer_corpus(tmp_path: Path, answer_text: str, name: str) -> Corpus:
    return load_nodes(
        tmp_path,
        [
            node("root", "branch", parent=None, contains=("a", "none")),
            node("a", "answer", parent="root", label="Tell me", answer=answer_text),
            node("none", "bottom", parent="root", label="None", answer="no authored answer"),
        ],
        name=name,
    )


def test_behavior_derives_from_corpus_not_engine_code(tmp_path: Path) -> None:
    before = _engine_source_hashes()

    corpus_a = _single_answer_corpus(
        tmp_path, "Answer A: TRUGS is executable English.", "a.trug.json"
    )
    corpus_b = _single_answer_corpus(tmp_path, "Answer B: the sky is blue.", "b.trug.json")

    answer_a = Engine(corpus_a, ScriptedSelector(["a"])).answer("same query")
    answer_b = Engine(corpus_b, ScriptedSelector(["a"])).answer("same query")

    # behavior changed — driven purely by the corpus edit
    assert answer_a.text != answer_b.text
    assert answer_a.text.startswith("Answer A")
    assert answer_b.text.startswith("Answer B")

    # ...and the engine source is untouched (D7 acid): no engine-module file differs
    assert _engine_source_hashes() == before
