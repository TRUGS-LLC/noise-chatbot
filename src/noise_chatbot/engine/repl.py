"""A terminal chat REPL driving the engine directly (the library path).

<trl>
FUNCTION repl SHALL RECEIVE MESSAGE query FROM PARTY user THEN SEND RECORD answer TO PARTY user.
</trl>

Reads a query per line, walks the corpus, and prints the pre-authored answer with its
provenance path. The REPL never composes or rewrites answer text — it prints exactly what
the engine delivers. The default backend is the offline deterministic ``KeywordSelector``
(no network / key); ``--backend anthropic`` selects the forced-tool backend via a lazy
import, so importing this module never pulls the ``anthropic`` SDK (ADR-002).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from noise_chatbot.corpus import CorpusError, load_corpus
from noise_chatbot.engine.core import Engine
from noise_chatbot.engine.select import KeywordSelector
from noise_chatbot.engine.select.port import Selector
from noise_chatbot.stores.gap import InMemoryGapStore

_PROMPT = "you> "


def _build_selector(backend: str) -> Selector:
    if backend == "anthropic":
        # Lazy import — keeps the base install SDK-free (ADR-002).
        from noise_chatbot.engine.select.anthropic import AnthropicSelector

        return AnthropicSelector()
    return KeywordSelector()


def run(
    corpus_path: str | Path, *, backend: str = "keyword", lines: Iterable[str] | None = None
) -> None:
    """Drive the engine over ``lines`` (or stdin), printing each answer + provenance."""
    corpus = load_corpus(corpus_path)
    engine = Engine(corpus, _build_selector(backend), gap_store=InMemoryGapStore())

    source = lines if lines is not None else _stdin_lines()
    for query in source:
        query = query.strip()
        if not query:
            continue
        if query in {"quit", "exit"}:
            break
        answer = engine.answer(query)
        print(answer.rendered())
        print()


def _stdin_lines() -> Iterable[str]:
    print(f"noise-chat — ask a question, or 'quit' to exit.\n{_PROMPT}", end="", flush=True)
    for line in sys.stdin:
        yield line
        print(_PROMPT, end="", flush=True)


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point (``noise-chat``)."""
    parser = argparse.ArgumentParser(
        prog="noise-chat", description="TRUG-traced answer engine REPL"
    )
    parser.add_argument("corpus", help="path to a trug-VALID corpus (.trug.json)")
    parser.add_argument(
        "--backend",
        choices=("keyword", "anthropic"),
        default="keyword",
        help="selection backend (default: offline keyword)",
    )
    args = parser.parse_args(argv)
    try:
        run(args.corpus, backend=args.backend)
    except CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
