#!/usr/bin/env python3
"""Latency benchmark harness (Phase 7 / B5) — measured p50/p95/p99 per backend.

<trl>
ASSERT PROCESS engine SHALL RETURN RECORD answer WITHIN 3s.
</trl>

Measures the wall-clock of a full ``engine.answer`` (the complete-answer latency, incl.
the selection backend's round-trips) over N samples against the demo corpus, and writes
``scripts/bench_results.json`` in the ``bench_results.v1`` schema the Phase-8 SC-8 recipe
parses. The 3 s ASSERT is *measured* here, never asserted.

Run (needs ANTHROPIC_API_KEY for the anthropic backend):
    python scripts/bench_latency.py --backends anthropic --n 30
The local backend is measured only when a GGUF model path is supplied via --local-model.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from noise_chatbot.corpus import load_corpus
from noise_chatbot.engine import Engine
from noise_chatbot.stores.gap import InMemoryGapStore

if TYPE_CHECKING:
    from noise_chatbot.engine.select.port import Selector

CORPUS = "examples/faq_demo/faq.trug.json"
OUT = "scripts/bench_results.json"

# A realistic FAQ query mix that exercises 1-fork and 2-fork walks + a ⊥.
QUERIES = [
    "what is trugs?",
    "how does the answer engine choose an answer?",
    "can this thing hallucinate an answer?",
    "what happens when there is no good answer?",
    "is my chat actually encrypted?",
    "tell me something completely unrelated to any of this",
]


def _percentile(samples_ms: list[float], pct: float) -> float:
    """Nearest-rank percentile in milliseconds (ceil rank, 1-indexed)."""
    ordered = sorted(samples_ms)
    rank = max(1, min(len(ordered), math.ceil((pct / 100.0) * len(ordered))))
    return ordered[rank - 1]


def _backend_errored(answer: object) -> bool:
    """True if any selection attempt returned the empty-string failure sentinel.

    A backend failure (timeout / rate-limit / auth) makes AnthropicSelector return "",
    which shows up as an off-menu attempt — distinguishing a *failed call* from a genuine
    LLM-selected ⊥. Measuring failed calls would report meaningless (fast) latency.
    """
    trace = getattr(answer, "trace", None)
    steps = getattr(trace, "steps", [])
    return any(attempt.choice == "" for step in steps for attempt in step.attempts)


def _measure(
    selector: Selector, corpus_path: str, n: int, *, warmup: int = 2, show: int = 0
) -> dict[str, float | int]:
    corpus = load_corpus(corpus_path)
    engine = Engine(corpus, selector, gap_store=InMemoryGapStore())
    # Warm the connection (TLS + first request) so cold-start doesn't skew the tail —
    # the client reuses the connection, so steady-state is what the p95 target measures.
    for i in range(warmup):
        engine.answer(QUERIES[i % len(QUERIES)])
    samples: list[float] = []
    errors = 0
    for i in range(n):
        query = QUERIES[i % len(QUERIES)]
        start = time.perf_counter()
        answer = engine.answer(query)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        samples.append(elapsed_ms)
        if _backend_errored(answer):
            errors += 1
        if i < show:
            trail = " > ".join(answer.address)
            print(f"    [{elapsed_ms:6.0f} ms] {query!r} -> {trail} (bottom={answer.is_bottom})")
    if errors > n // 10:  # >10% of walks hit a failed call → the numbers are meaningless
        raise RuntimeError(
            f"backend appears to be failing: {errors}/{n} walks got no valid selection "
            f"(empty choice — likely rate-limit / auth / credit). Latency measurement is "
            f"invalid; refusing to write results. Wait for the limit to reset and re-run."
        )
    return {
        "p50_ms": round(_percentile(samples, 50)),
        "p95_ms": round(_percentile(samples, 95)),
        "p99_ms": round(_percentile(samples, 99)),
        "n": n,
    }


def _anthropic_selector(model: str | None) -> Selector:
    from noise_chatbot.engine.select.anthropic import AnthropicSelector

    return AnthropicSelector(model=model) if model else AnthropicSelector()


def _local_selector(model_path: str) -> Selector:
    from noise_chatbot.engine.select.local import LocalSelector

    return LocalSelector(model_path=model_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="p50/p95/p99 latency per selection backend")
    parser.add_argument("--backends", default="anthropic", help="comma list: anthropic,local")
    parser.add_argument("--n", type=int, default=50, help="timed samples per backend (default 50)")
    parser.add_argument("--warmup", type=int, default=2, help="untimed warmup walks (default 2)")
    parser.add_argument("--model", default=None, help="anthropic model override")
    parser.add_argument(
        "--local-model", default=None, help="path to a local GGUF model (enables local)"
    )
    parser.add_argument("--corpus", default=CORPUS)
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args(argv)

    wanted = [b.strip() for b in args.backends.split(",") if b.strip()]
    backends: dict[str, dict[str, float | int] | None] = {"anthropic": None, "local": None}

    if "anthropic" in wanted:
        print(f"measuring anthropic backend ({args.n} samples)...")
        backends["anthropic"] = _measure(
            _anthropic_selector(args.model), args.corpus, args.n, warmup=args.warmup, show=3
        )
    if "local" in wanted:
        if not args.local_model:
            print("skipping local backend: no --local-model GGUF path supplied")
        else:
            print(f"measuring local backend ({args.n} samples)...")
            backends["local"] = _measure(
                _local_selector(args.local_model), args.corpus, args.n, warmup=args.warmup
            )

    results = {
        "schema": "bench_results.v1",
        "corpus": args.corpus,
        "date": date.today().isoformat(),
        "backends": backends,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    anthropic = backends["anthropic"]
    if anthropic is not None:
        p95 = anthropic["p95_ms"]
        verdict = "PASS" if p95 < 3000 else "OVER LIMIT"
        print(f"\nanthropic: p50={anthropic['p50_ms']}ms p95={p95}ms p99={anthropic['p99_ms']}ms")
        print(f"  RETURN answer WITHIN 3s (B5): p95 {p95}ms < 3000ms -> {verdict}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
