# How the TRUG-traced answer engine works

A short, honest explanation of what this engine is — and, just as important, what it is
**not**.

## The one idea: the graph is the program

A corpus is a `trug validate`-VALID TRUG graph. The engine executes it as a program. It
is a decision tree of human-authored content:

- **branch** nodes are forks (a menu of options),
- **answer** nodes are leaves holding pre-written answer text,
- **bottom** (⊥) nodes are the authored "no answer covers this" floor,
- **procedure** nodes are reserved for V2 (the engine refuses to execute them).

To answer a query, the engine starts at the root and walks down: at each fork it
enumerates the legal child options (a *menu*), a selection backend picks exactly one, and
the walk descends. When it reaches a leaf, it delivers that leaf's authored text
**verbatim**, tagged with its node-id path as a **provenance address**
(e.g. `root > engine > how_it_walks`).

## What the model does — and doesn't

This is the part that's easy to get wrong, so it's worth being precise:

- **The model does not write answers. It picks them.** At each fork, the selection
  backend is handed the menu and returns exactly one option. That's its entire job — one
  bounded, multiple-choice decision per fork.
- **The answer text is authored by a human**, in the corpus. The engine never generates,
  paraphrases, or rewrites it.
- **The choice is *constrained* to the menu**, not merely requested. With the Anthropic
  backend it's a forced tool-call whose schema enumerates the legal ids; with the local
  backend it's a GBNF grammar (`root ::= "id_a" | "id_b" | …`) that restricts the model's
  output token-by-token. Either way the model *cannot* emit free text or an off-menu id.
  And the engine re-validates membership regardless of backend — if a returned id isn't on
  the menu, it retries once, then routes to ⊥.

So "the LLM answers the question" is the wrong mental model. **A human writes the answers;
the LLM routes to one of them.**

## Why it can't hallucinate

There is **no generation step between source and delivery.** The delivered text is always
a pre-authored leaf. That has a sharp consequence:

- A **wrong** answer is still possible — the model can pick the wrong option at a fork.
- But a wrong answer is **located, not silent**: the provenance address shows exactly
  which leaf was delivered, so a mis-selection is visible and traceable.
- A query with no good answer routes to an authored ⊥ node and writes a **located gap
  record** (which node the walk died at, and the raw query) for a human to author against
  later — it never invents an answer.
- An **invented** answer is structurally impossible: there is no code path that composes
  answer text.

This is the whole point. Wrong-but-located beats plausible-but-fabricated.

> **Worked example (real, from the demo).** Running the tiny local model on
> `examples/faq_demo/`, the query *"is my chat encrypted?"* mis-routed to the
> *"what is TRUGS"* answer instead of the crypto one — a genuine wrong pick. But the
> provenance made the error visible (`root > what_is_trugs`), and the delivered text was
> still a real, human-written answer, not a fabrication. The system failed honestly.

## Backends: the safety is architectural, not model-tier

The same guarantee holds no matter what does the picking:

| Backend | Where it runs | Constraint mechanism | Needs |
|---|---|---|---|
| **Anthropic** (`[anthropic]`) | Anthropic's servers | forced tool-choice over the menu enum | API key, per-call cost |
| **Local** (`[local]`) | your CPU, offline | GBNF grammar over the menu enum | a GGUF model file (~hundreds of MB up) |

Because safety comes from the architecture (menu-membership + ⊥ routing) rather than the
model, you can run the engine with **zero cloud dependency** and keep the same
no-hallucination property. That's the cost-decoupling thesis, demonstrated end-to-end.

**But routing *quality* is a different axis from routing *safety*.** A weak selector
(e.g. a 0.5B local model) will mis-route more often than a strong one — every such error
is safe and located, but it's still the wrong answer. Picking a selection model is a
quality/cost tradeoff, and **what size a realistic corpus actually needs is an open
question under active evaluation** (see the model-sizing study issue). The 0.5B demo above
proves the *safety* property on the smallest plausible hardware; it is **not** a claim
that a 0.5B model routes *well*.

## The acid test

Every behavior change ships as a **corpus edit**, never an engine-code edit. The engine
has zero domain knowledge; the corpus is the program. If you want the chatbot to say
something different, you edit the TRUG and re-run `trug validate` — you do not touch the
interpreter.

## Try it

```bash
pip install "noise-chatbot[engine]"              # the corpus validate gate (trug CLI)
noise-chat examples/faq_demo/faq.trug.json       # offline keyword backend

pip install "noise-chatbot[engine,anthropic]"    # + the cloud selection backend
noise-chat examples/faq_demo/faq.trug.json --backend anthropic   # needs ANTHROPIC_API_KEY
```

## See also

- [`docs/corpus_schema.md`](corpus_schema.md) — the corpus contract (node roles, ⊥
  routing, versioning).
- [`examples/faq_demo/`](../examples/faq_demo/) — the demo corpus this page's examples use.
- [`scripts/bench_latency.py`](../scripts/bench_latency.py) — the latency benchmark
  (measures p95 complete-answer latency per backend).
