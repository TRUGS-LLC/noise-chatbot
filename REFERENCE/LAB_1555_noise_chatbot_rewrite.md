# LAB — noise-chatbot Python rewrite (TRUG-driven)

**Issue:** [#1555](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1555)
**EPIC sub-issue:** [#1548 S9](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1548)
**Sibling:** [#1550 — Go repo transfer + AGPL relicense](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1550)
**Started:** 2026-04-16
**Status:** PLANNING — Phase A (super-TRUG authoring) scoped, awaiting VALIDATION
**Methodology:** `TRUGS-LLC/TRUGS/REFERENCE/PAPER_how_to_code_with_trugs.md` (§2 greenfield, §3 refactoring, §5 AAA)

---

## What this file is

Running lab book for the noise-chatbot Python rewrite. Captures vision, per-phase plan, decisions log, open questions, and references. **GitHub Issue #1555 is the source of truth for task state and HITM gates**; this file is the long-form mirror — survives GitHub outages, greppable locally, commits with each session update.

Do not put transient status here. Do put: why we chose X over Y, what we learned, what we'd do differently.

---

## Vision

Rewrite the Go noise-chatbot in Python with full behavioral parity, targeting `TRUGS-LLC/noise-chatbot` as an Apache-2.0 public release. The Python version consumes `trugs-store` as its persistence backend — validating the S8 payoff and making noise-chatbot the first downstream consumer of trugs-store in production.

**The rewrite doubles as a methodology proof.** We will author a complete standalone TRUG of the Go code (the "super-TRUG") that captures every observable behavior without touching the Go source. Then we regenerate Python from the TRUG, using it as the authoritative spec. If a Python implementer given only the super-TRUG + the TRL vocabulary can produce a passing implementation, TRUGs are validated as a code-generation specification format — which underwrites the broader TRUGS thesis.

Not this project's goal: benchmarking, performance parity beyond order-of-magnitude, re-architecting the chatbot.

---

## Feasibility — GO

| Check | Verdict | Notes |
|---|---|---|
| Can we author a full-coverage super-TRUG of the Go code? | **YES** | Black-box spec, not in-place refactor. Function-level TRL preambles + cross-module edges. Paper §3 Steps A–E adapted for external observer. |
| Does trugs-store cover the Go chatbot's persistence needs? | **LIKELY YES** | Need to enumerate Go persistence surface in Phase A step A3. If gaps exist, filed as trugs-store issues, not blockers to Phase A. |
| Feature parity achievable by one engineer with LLM assistance? | **YES** | Go repo 17MB includes vendor/deps. Core logic is likely <5K LOC — confirm in Phase A step A1. |
| Licensing clean? | **YES** | Sole contributor Xepayac verified (18 commits). Apache → AGPL relicense for the Go repo is permitted. New Python code is fresh-written Apache-2.0. |
| `trugs-compliance-check` is Python-only — is that a blocker? | **NO** | Super-TRUG is a standalone JSON artifact; doesn't need Go language support. Compliance gates apply to the Python implementation (Phase B+), not the spec. |
| Cross-language semantic drift | **MITIGATED** | Behavior-parity test corpus authored in Phase A against Go as golden reference; runs against both implementations in Phase B. |

**Decision: GO.** No blocking risks.

---

## Phase plan

Six phases. Only Phase A is specified in detail below — subsequent phases get their own SPECS/ARCH comments on #1555 when they become active.

| # | Phase | Output | Gate |
|---|---|---|---|
| A | Super-TRUG authoring | `noise_chatbot.super.trug.json` + behavior-parity test corpus (Go-golden) | Human VALIDATION — can a reader implement Python from TRUG alone? |
| B | Python scaffold | New repo at `TRUGS-LLC/noise-chatbot` with `pyproject.toml`, CI, Dark Code baseline, `trugs-store` dependency wired | CI green, `trugs-compliance-check --strict` = 100% on empty scaffold |
| C | Python implementation | Module-by-module impl from super-TRUG. No reading Go source during this phase — if TRUG gaps surface, return to Phase A | Behavior-parity corpus passes 100% against Python |
| D | Go repo move (via #1550) | `TRUGS-LLC/noise-chatbot` → `Xepayac/noise-chatbot-go`, Apache → AGPL | #1550 closed |
| E | Public release | `TRUGS-LLC/noise-chatbot` 0.1.0 on PyPI, compliance 100% strict | Human merges release PR |
| F | Methodology retrospective | `REPORT_trug_driven_rewrite.md` in TRUGS-DEVELOPMENT/REFERENCE/ | Shipped |

---

## Phase A — detailed plan (active)

**Goal:** Produce a standalone `noise_chatbot.super.trug.json` that a competent engineer, given only (TRUG + TRL vocabulary + the paper), can translate into a Python implementation that passes the behavior-parity test corpus. Go source is not used during implementation — it is used here, in Phase A, to extract the spec.

### A1 — Inventory the Go surface area

- Clone `TRUGS-LLC/noise-chatbot` locally (read-only; no edits to Go code during Phase A)
- `cloc` / `tokei` to get LOC by package, excluding vendor
- Catalog:
  - Every exported function + type + interface (method receivers included)
  - Every CLI subcommand + flag + config key (cobra/viper patterns)
  - Every HTTP route + request/response shape (if applicable)
  - Every goroutine boundary + channel (concurrency model)
  - Every persistence operation (SQL, filesystem, network)
  - Every external dependency (imports + module versions)
  - Every error type + wrapping pattern
- **Output:** `A1_inventory.md` — flat enumeration, no analysis yet. Committed as part of the Phase A deliverable (or as an appendix comment on #1555).

### A2 — Translate per-symbol to TRL sentences (paper §3 Step B)

For each item in the A1 inventory:

- Write a one-sentence plain English summary of what it does
- Translate to a TRL sentence using vocabulary from `TRUGS_PROTOCOL/` and the 190-word list
- Note where the TRL vocabulary is insufficient — these become `[VOCAB-GAP]` markers for eventual resolution (may force rephrasing or a TRL spec issue)

### A3 — Build the super-TRUG (paper §3 Step C, scaled)

Structure:

```
noise_chatbot.super.trug.json
├── nodes
│   ├── STAGE nodes for each top-level pipeline
│   ├── FUNCTION nodes for every exported Go function (trl property = sentence from A2)
│   ├── SERVICE nodes for long-running components (daemon, listeners)
│   ├── INTERFACE nodes for public HTTP routes + CLI commands
│   ├── RESOURCE nodes for persistent artifacts (files, DB tables, keys)
│   └── RECORD nodes for data types (structs)
├── edges
│   ├── FEEDS/ROUTES for data flow
│   ├── DEPENDS_ON for cross-module references
│   ├── IMPLEMENTS for interface satisfaction
│   └── CONTAINS for module/package hierarchy
└── hierarchy
    └── parent-child matching the Go package structure
```

Invariants and preconditions go on node `properties`, not as edges.

Validation: `trugs-folder-check noise_chatbot.super.trug.json` — schema must pass. Function count must match A1. Zero dangling edges. No invented TRL relations (CLAUDE.md rule).

### A4 — Author the behavior-parity test corpus

For every FUNCTION / INTERFACE node with observable behavior:

- Write test cases as YAML/JSON fixtures: input → expected output
- Express as `AGENT SHALL VALIDATE ...` TRL sentences
- Run each fixture against the Go binary (golden) to capture reference output — this is the ground truth for Phase C
- Fixtures + runner live under `tests/parity/` in the Phase A deliverable; Phase C reuses them verbatim against the Python impl

Coverage bar: every public function in A1 gets at least one parity fixture. Error paths get fixtures. Concurrency invariants (race-free, ordering, backpressure) get fixtures where observable from the outside.

### A5 — VALIDATION gate (HITM)

Package Phase A outputs as a single PR against `TRUGS-DEVELOPMENT/REFERENCE/`:

- `noise_chatbot.super.trug.json`
- `A1_inventory.md` (or equivalent appendix)
- `tests/parity/*.yaml` + runner + a `README.md` on how to run against Go
- Updated LAB file with decisions log + open questions surfaced during A1–A4

The human reads the super-TRUG and asks: *"Could I implement Python from this alone?"* If not, Phase A returns to A2/A3 for gap-filling. If yes, VALIDATION passes and Phase B kicks off.

### Deliverable locations (confirmed 2026-04-16)

- `TRUGS-DEVELOPMENT/REFERENCE/` — frozen reference copy (the "lab book" home)
- Commit to `TRUGS-LLC/noise-chatbot` (Go repo) before transfer — travels with the Go code to `Xepayac/noise-chatbot-go`
- Later: re-commit into `TRUGS-LLC/noise-chatbot` (Python) as the spec the rewrite was built from

---

## Decisions log

### 2026-04-16

- **New portfolio category: "launched stable external dependency"** — TRUGS-STORE is the first. Consumed via PyPI, not developed locally. Future bugfixes: fresh clone, fix, PR, publish, delete. Do not nest external live repo clones inside TRUGS-DEVELOPMENT.
- **S9 scope inversion** — was "transfer Go repo to Xepayac (internal)"; now "Python rewrite replaces Go in the public slot; Go moves to Xepayac/noise-chatbot-go under AGPL." Driver: chatbot is the first revenue bridge and the consumer of trugs-store, so it belongs in the portfolio and must be Python + Dark Code compliant.
- **Super-TRUG style: standalone black-box spec** — not an in-place Go refactor per paper §3. Reason: `trugs-compliance-check` is Python-only in v1; standalone spec is language-agnostic and unblocks Phase A immediately. An in-place Go compliance pass is deferred indefinitely (likely never).
- **Behavior-parity corpus: authored in Phase A, not Phase B** — forces the TRUG to name every testable behavior. Phase A is the only phase where we read Go source; Phase C is TRUG-only. Keeps the methodology honest.
- **Lab book mirror pattern** — Issue body = SoT for task state; `REFERENCE/LAB_*.md` = long-form decisions/provenance. This is the first project large enough to warrant the split; pattern may standardize for future multi-phase AAA projects.
- **License split** — Python `TRUGS-LLC/noise-chatbot` Apache-2.0 (portfolio standard). Go `Xepayac/noise-chatbot-go` Apache-2.0 → AGPL-3.0 (defensive for internal/reference impl). Apache-outbound-to-AGPL relicense is permitted because Xepayac is sole contributor (verified 18/18 commits).
- **Go repo archive vs nested clone** — earlier in this session, we moved the nested clone at `TRUGS-DEVELOPMENT/TRUGS-STORE/` to `zzz_ARCHIVE/zzz_2604_TRUGS-STORE/` as a 30-day hedge against deletion. Pattern to adopt for any future external-repo local clones that stop being needed.

---

## Open questions

- **Release name on PyPI** — `noise-chatbot` (matches repo), `trugs-chatbot` (aligns naming with trugs-store / trugs-memory), or something user-facing (decide during Phase B per the methodology paper's naming guidance).
- **Concurrency translation** — Go goroutines + channels → Python asyncio vs threading vs multiprocessing. Likely asyncio, but the super-TRUG must describe the concurrency model precisely enough that this choice is downstream, not upstream, of the spec. Surface concrete cases during A1.
- **TRUG/L vocabulary gaps** — any Go feature without a clean TRL expression (e.g. select statements, defer, panic/recover). If surfaced in A2, file against `TRUGS-LLC/TRUGS` to extend the spec. Do not invent vocabulary.
- **Go binary distribution** — does `TRUGS-LLC/noise-chatbot` ship a binary, a container, or source-only? Affects A1 inventory scope (deploy tooling is part of the interface or not).
- **Super-TRUG reviewer** — Phase A5 VALIDATION is harder than usual. A reviewer who already knows Go can unconsciously fill gaps from memory. Consider a second reviewer who doesn't know Go. Defer decision to Phase A5.

---

## References

- `TRUGS-LLC/TRUGS/REFERENCE/PAPER_how_to_code_with_trugs.md` — methodology (§2 greenfield, §3 refactoring, §5 AAA integration)
- `TRUGS-LLC/TRUGS/REFERENCE/PAPER_dark_code.md` — the *why*
- `TRUGS-LLC/TRUGS/REFERENCE/STANDARD_dark_code_compliance.md` — compliance checks C1–C7
- `REFERENCE/REFERENCE_aaa_reference.md` — AAA protocol details
- `.claude/rules/aaa-protocol.md` — 9 phases, 2 cycles, HITM gates
- `TRUGS_PROTOCOL/TRUGS_CORE.md` — 7 node fields / 3 edge fields, invariant foundation
- 190-word TRL vocabulary — `CLAUDE.md` §"TRUGS Language (TRL)"

---

## Update protocol

Append to **Decisions log** when a judgment call lands.
Append to **Open questions** when something surfaces without a clean answer.
Move items from Open questions to Decisions log when resolved.
Do not rewrite history — the log is append-only.

Update **Status** line at the top when phase transitions. Commit on a branch per session update; no direct-to-main.
