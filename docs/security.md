# The noise-chatbot security model

What this system guarantees, the layered mechanisms that enforce it, and — just as
important — what it deliberately does **not** guarantee.

The headline: **noise-chatbot's executional-integrity property is now *warranted*, not
merely asserted.** A third party can take a corpus and a recorded trace and *re-run the
check themselves* — `verify_trace(corpus, trace)` re-derives the walk's legality from the
corpus's own content-digest and returns a verdict. The safety of an answer is no longer a
claim in a README; it is a re-runnable function, and it has been independently audited.

This page is the security counterpart to [`docs/how-it-works.md`](how-it-works.md): that
page explains the engine; this one explains why it is safe.

---

## The property, in one sentence

> Every delivered answer is a **human-authored** leaf reached by a **legal walk** of a
> **specific, content-identified** corpus — and any party holding the corpus and the
> trace can **verify** that after the fact, without re-running (or trusting) the model.

Everything below is a layer that makes that sentence true and checkable.

---

## The eight security systems

The guarantee is not one mechanism; it is a stack. Each layer is load-bearing, and the
top layer (`verify_trace`) is what turns the whole stack from *design intent* into a
*proof you can re-run*.

### 1. LLM-never-composes — the foundation

There is **no generation step between source and delivery.** Answer text is written by a
human in the corpus and delivered **verbatim**; the engine never generates, paraphrases,
or rewrites it. The model's entire job is to **pick** one option at a fork — a bounded,
multiple-choice decision — never to **write**.

The sharp consequence: an *invented* answer is structurally impossible (there is no code
path that composes text), a *wrong* answer is still possible but **located, not silent**
(the provenance address names the exact leaf delivered), and a query with no good answer
routes to an authored ⊥ ("no answer covers this") node and records a located gap for a
human to author against later. Wrong-but-located beats plausible-but-fabricated.

*See [`docs/how-it-works.md` § Why it can't hallucinate](how-it-works.md).*

### 2. Constrained selection — menu-membership, bounded retry, ⊥ routing

The pick is **constrained to the menu**, not merely requested of the model:

- **Anthropic backend** — a forced tool-call whose schema enumerates the legal ids.
- **Local backend** — a GBNF grammar (`root ::= "id_a" | "id_b" | …`) that restricts
  output token-by-token.

Either way the model *cannot* emit free text or an off-menu id — and the engine
**re-validates membership regardless of backend**. If a returned id isn't on the menu, it
retries once, then routes to ⊥. Safety is **architectural** (menu-membership + ⊥
routing), not a property of the model tier: the same guarantee holds fully offline on a
tiny local model. Routing *quality* is a separate axis from routing *safety* — a weak
selector mis-routes more often, but every such error is safe and located.

### 3. Session-gated legality — one oracle, no drift

What moves are legal at a node is decided by a single, pure, public function —
[`legal_menu(corpus, node_id, session)`](../src/noise_chatbot/engine/legal_menu.py). It
returns a node's children with any **protected** node the session lacks a capability for
**excluded**. A [`Session`](../src/noise_chatbot/engine/session.py) is an immutable set of
capabilities keyed by node id; the default V1 session is anonymous (grants nothing, so
every protected subtree is excluded).

The load-bearing detail: the engine's own enumerator **delegates** to `legal_menu`, and
the checker (`verify_trace`) re-derives the menu by calling the **same** function — so the
engine's gate and the checker's gate **can never drift.** The ungated `Corpus.children`
view is deliberately *not* the legality menu: it would leak protected children, and a
checker built on it would bless walks the engine refuses.

### 4. Corpus content identity — `corpus_digest`

At load, the corpus is reduced to a content-address digest —
[`Corpus.corpus_digest`](../src/noise_chatbot/corpus/loader.py), a `tci1-sha256-…` value
computed via `trugs_tools.digest` (the substrate's shared-spine **artifact_identity**, an
order-invariant layered fold). The `Corpus` is a **frozen** dataclass, computed once at
load and never mutated by the engine, so a walk is bound to a *specific, immutable*
corpus. Two corpora that differ in any authored text or structure produce *different*
digests; because the identity is order-invariant, two byte-orderings of the *same* content
produce the *same* digest — that is what makes it a true interop identity, not a private
hash.

### 5. The complete trace — a self-contained, checkable record (schema v2)

A walk records a [`TraceLog`](../src/noise_chatbot/engine/trace.py). As of schema **v2**
the trace is *self-contained* — it carries everything a third party needs to re-derive the
walk without the engine:

- **`corpus_digest`** — the exact corpus this walk is bound to (layer 4).
- **`grants`** — the session grant-set that gated every menu, sorted for a stable record
  (so the session-gated menu is independently re-derivable).
- **`terminal`** — the delivered leaf (`{leaf_id, is_bottom}`); recording it copies an
  *id*, never authored text.
- Plus the per-fork `steps` (cursor, presented `menu_ids`, and each selection attempt).

All three v2 additions are opt-in with defaults, so a digest-less **v1** trace still
constructs byte-identically and remains checkable for legality (reported *unbound*).

### 6. `verify_trace` — the executional-integrity checker (the payoff)

[`verify_trace(corpus, trace)`](../src/noise_chatbot/engine/verify.py) returns a
`Verdict{legal, bound}`. It is what makes the property **warranted**: a re-runnable check
that a trace is a legal walk of the graph bearing this corpus's digest. It is a **total,
offline read** — no network, no key, no model weights. What it enforces:

- **Re-derived legality (the digested corpus is the oracle, not the trace).** At each step
  it re-derives the menu via `legal_menu` and rejects a trace whose self-reported
  `menu_ids` disagree — so a **forged menu** smuggling an off-corpus option cannot pass.
  Each recorded choice must be a member of the *re-derived* menu.
- **Contiguity.** Each step is taken at the cursor the prior legal descent actually
  reached; a truncated or spliced walk is rejected.
- **Terminal binding (RT-2).** The recorded terminal leaf is bound to the endpoint the
  verified walk reaches — the *delivered* answer is tied to the legal walk, not
  self-reported. A **forged terminal** (on the answer path *or* a ⊥ route) is rejected, and
  a digest-bearing trace **cannot strip** its terminal to dodge the binding (the downgrade
  defense).
- **Digest binding.** `bound` is true only when the trace names the digest of *this* exact
  corpus; a mismatched or digest-less trace reports `unbound` (still checkable for
  legality).
- **Membership-only, replay-only.** It validates *membership* and produces **no answer
  text** (LLM-never-composes is structural here — there is no generation path), and it
  **never re-invokes any selection backend**, so its verdict is independent of the model's
  sampling.

Because the engine and the checker share the `legal_menu` oracle, "the engine would have
allowed this walk" and "the checker accepts this walk" are the same question.

### 7. Wire provenance — out-of-band, contract-preserving, thread-safe

When served, a CHAT response carries walk **provenance** —
`{corpus_digest, address}` — on an *optional, omit-when-unset* field of the wire
[`Message`](../src/noise_chatbot/protocol/message.py) (mirroring `reply_to`), so a
Go/legacy client that doesn't know the key ignores it and byte-parity holds. Crucially the
provenance rides **out-of-band**: the classifier's `Callable[..., list[str]]` contract is
**never widened** (it still returns node ids), and the engine
[adapter](../src/noise_chatbot/engine/adapter.py) carries the walk provenance on a
**per-call thread-local channel** read via an adapter-identity check — so the server's
concurrent per-connection threads, which share one classifier, never see each other's
provenance, and a non-engine classifier carries none.

### 8. Fail-honest degradation

An engine exception yields an **honest non-answer** (an empty id list → the server's
no-match reply), never a crash of the serve loop and never a *silent* fallback to a flat
keyword classifier. Degradation to a keyword classifier remains an **explicit, opt-in
operator choice** — visible, never automatic. Failing loud beats failing plausible.

---

## Why the property is *warranted* (not just asserted)

`verify_trace` was built and then **independently audited** as the Phase-10 acceptance gate
of its design record (AAA #69):

- **Two independent auditors**, working cold, converged on **GO** — zero CRITICAL, zero
  unaccepted HIGH.
- A **red-team** auditor attacked the shipped checker with a 22-case forgery battery, a
  **12,000-walk differential fuzz**, and a **2,000-iteration concurrency stress**, and
  could not break it: every forged menu, forged choice, forged terminal, phantom step, and
  downgrade-stripped terminal was rejected, each with a passing adversarial negative test.
- A **verification** auditor confirmed the shipped test suite adds coverage with **zero
  regression** and that all six load-bearing invariants (LLM-never-composes, re-derived
  legality, terminal binding, digest binding, replay-only, frozen corpus) hold.

An assertion you cannot re-run is a promise. A checker anyone can re-run — that survived
adversarial fuzzing — is a warrant.

---

## What this does **not** do (honest limits)

The model is deliberately narrow. It is integrity and provenance, not confidentiality or
authentication:

- **It is hash-based, not encrypted and not signed.** The guarantees rest on a
  content-address digest (`tci1-sha256`), which proves *which* corpus a walk is bound to —
  **not** confidentiality of the content and **not** the authorship/authenticity of the
  trace. A trace is **not cryptographically signed**: anyone holding the corpus can compute
  its digest and construct a `bound` trace. The containment that still holds is the
  important part — see the next point.
- **A forgery can only ever surface a real authored node.** Because `verify_trace`
  re-derives legality from the corpus, the worst a forged trace can do is name an authored
  node the corpus already contains — **never** an off-corpus id, **never** fabricated text.
  LLM-never-composes survives even an unsigned, attacker-constructed trace.
- **It is not an entitlement / access-control oracle.** The recorded grant-set is
  *unauthenticated*: a forged grant-set re-derives a wider (protected) menu. `verify_trace`
  validates legality *under the recorded session*, not whether the caller was *entitled* to
  that session. Access control is a separate concern.
- **It does not check engine policy the trace doesn't record.** The retry bound
  (`RETRY BOUNDED 1`) is an `Engine` parameter absent from the trace, so a walk with extra
  recorded retries still reads as legal.
- **The wire carries `{corpus_digest, address}`, not the full trace.** A wire consumer can
  see *where* an answer came from, but cannot itself run `verify_trace` from the response
  alone — verification takes the full trace as input.
- **Digest *correctness* is trusted, not re-derived here.** The `tci1-sha256` construction
  is owned and tested upstream (`trugs-tools`); this repo asserts the digest's shape,
  identity, and stability, not the RFC-8785 / layered-fold internals.
- **Routing quality is not safety.** A weak selector mis-routes more often; every such
  error is safe and *located*, but it is still the wrong (authored) answer.
- **Procedure leaves are refused, not executed.** Procedure nodes are reserved for V2; the
  engine routes them to ⊥ rather than executing anything.

---

## See also

- [`docs/how-it-works.md`](how-it-works.md) — how the engine walks the corpus and why it
  can't hallucinate.
- [`docs/corpus_schema.md`](corpus_schema.md) — the corpus contract (node roles, ⊥
  routing, capabilities, versioning).
- Source of the guarantees:
  [`engine/verify.py`](../src/noise_chatbot/engine/verify.py) (the checker),
  [`engine/legal_menu.py`](../src/noise_chatbot/engine/legal_menu.py) (the oracle),
  [`engine/trace.py`](../src/noise_chatbot/engine/trace.py) (the v2 trace),
  [`engine/session.py`](../src/noise_chatbot/engine/session.py) (capabilities),
  [`corpus/loader.py`](../src/noise_chatbot/corpus/loader.py) (`corpus_digest`).
