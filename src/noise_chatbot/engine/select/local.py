"""Local grammar-constrained selection backend (B3 / D4) — llama.cpp GBNF enum.

<trl>
FUNCTION selector SHALL RECEIVE RECORD menu THEN RETURN SOLE RECORD choice.
ASSERT PROCESS engine SHALL VALIDATE EACH RECORD choice BY RECORD menu.
</trl>

Constrained decoding is the correctness precondition (D4): a GBNF grammar
``root ::= "id_a" | "id_b" | ...`` restricts the model's output to exactly one menu
node-id at every sampling step, so a conforming local model cannot emit free text or an
off-menu id. As with the Anthropic backend, engine safety does not depend on that
conformance (B2): the engine re-validates membership, and any failure returns ``""`` →
the off-menu → RETRY BOUNDED 1 → ⊥ chain.

``llama_cpp`` is imported lazily (the ``[local]`` extra), so this module imports — and its
grammar builder is unit-tested — without the heavy dependency or any model weights.
Import explicitly: ``from noise_chatbot.engine.select.local import LocalSelector``.
"""

from __future__ import annotations

from typing import Any, Final

from noise_chatbot.engine.select.port import Menu

_NO_SELECTION: Final = ""


def _escape(node_id: str) -> str:
    return node_id.replace("\\", "\\\\").replace('"', '\\"')


def build_enum_grammar(node_ids: list[str]) -> str:
    """Return a GBNF grammar accepting exactly one of ``node_ids`` and nothing else.

    <trl>
    FUNCTION build_enum_grammar SHALL MAP ARRAY node_ids AS RECORD grammar.
    </trl>
    """
    if not node_ids:
        raise ValueError("cannot build an enum grammar from an empty menu")
    alternatives = " | ".join(f'"{_escape(node_id)}"' for node_id in node_ids)
    return f"root ::= {alternatives}\n"


class LocalSelector:
    """Constrained-decoding backend over a local GGUF model via ``llama-cpp-python``.

    Real-model conformance is the T5.2 manual checkpoint (needs a HITM-approved model
    download); CI never loads weights.
    """

    __slots__ = ("_llama", "_max_tokens")

    def __init__(
        self, *, model_path: str, n_ctx: int = 2048, max_tokens: int = 32, **llama_kwargs: Any
    ) -> None:
        from llama_cpp import Llama  # lazy — the [local] extra

        self._llama = Llama(model_path=model_path, n_ctx=n_ctx, verbose=False, **llama_kwargs)
        self._max_tokens = max_tokens

    def select(self, query: str, menu: Menu) -> str:
        from llama_cpp import LlamaGrammar

        legal_ids = [option.node_id for option in menu]
        try:
            grammar = LlamaGrammar.from_string(build_enum_grammar(legal_ids), verbose=False)
            completion = self._llama.create_completion(
                prompt=self._prompt(query, menu),
                grammar=grammar,
                max_tokens=self._max_tokens,
                temperature=0.0,
            )
            choice = str(completion["choices"][0]["text"]).strip()
        except Exception:
            # Any local-inference failure → signal ⊥ (B2), never crash the walk.
            return _NO_SELECTION
        return choice if choice in set(legal_ids) else _NO_SELECTION

    def _prompt(self, query: str, menu: Menu) -> str:
        options = "\n".join(f"- {option.node_id}: {option.menu_label}" for option in menu)
        return (
            f"User question:\n{query}\n\n"
            f"Options (id: label):\n{options}\n\n"
            f"Respond with exactly one id.\n"
        )
