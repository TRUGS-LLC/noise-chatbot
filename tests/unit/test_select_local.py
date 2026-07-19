"""SP5 local-backend grammar test (T5.1) — GBNF enum, no weights.

Verifies the GBNF enum grammar built from a menu accepts exactly the menu-id alphabet and
nothing else (D4). Pure — needs neither ``llama_cpp`` nor model weights; the real-model
conformance run is the T5.2 manual checkpoint.
"""

from __future__ import annotations

import importlib.util

import pytest

from noise_chatbot.engine.select.local import build_enum_grammar


def test_enum_grammar_lists_exactly_the_menu_ids() -> None:
    grammar = build_enum_grammar(["about", "engine", "root_none"])
    assert grammar.strip() == 'root ::= "about" | "engine" | "root_none"'


def test_enum_grammar_escapes_quotes_and_backslashes() -> None:
    grammar = build_enum_grammar(['a"b', "c\\d"])
    assert r'"a\"b"' in grammar
    assert r'"c\\d"' in grammar


def test_empty_menu_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty menu"):
        build_enum_grammar([])


@pytest.mark.skipif(
    importlib.util.find_spec("llama_cpp") is None,
    reason="llama-cpp-python not installed (the [local] extra); grammar parse check skipped",
)
def test_grammar_parses_under_llama_cpp() -> None:
    from llama_cpp import LlamaGrammar

    # from_string parses the GBNF without a model — proves the grammar is well-formed.
    LlamaGrammar.from_string(build_enum_grammar(["about", "root_none"]), verbose=False)
