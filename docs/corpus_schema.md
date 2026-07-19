# Corpus schema contract (v1 — experimental until 1.0)

> **Status: experimental.** This schema is public but **not frozen** (ADR-004). Any
> change bumps `corpus_schema_version`. Do not depend on stability until a `1.0`
> corpus schema is declared.

A **corpus** is the program the TRUG-traced answer engine executes. It is a standard
[TRUG envelope](https://github.com/TRUGS-LLC) — `name` / `version` / `type` /
`dimension` / `dimensions` / `nodes` / `edges` — that is **`trug validate`-VALID before
role parsing begins** (the ADR-001 gate: the loader shells out to the published `trug`
CLI from `trugs-tools==2.1.0`, and refuses any file that is not `VALID`).

On top of a VALID envelope, the engine imposes the role contract below. A corpus that
is `trug`-VALID but violates any row is refused at load with a `CorpusSchemaError` — the
loader **never** loads an invalid corpus, and it defines **no writer** (corpora mutate
only via a human author → `trug validate` → a new version; capture-never-compose, D8).

## Versioning

The corpus carries its engine-schema version at the **root node**:

```json
"properties": { "corpus_schema_version": "1", "role": "branch" }
```

`corpus_schema_version` is **required** (`FUNCTION loader SHALL REQUIRE RECORD
schema_version FROM EACH FILE corpus`). This engine supports version `"1"` only; any
other value is refused.

## Node roles

Every node carries `properties.role` ∈ `{ branch, answer, bottom, procedure }`. An
unknown or missing role is **INVALID at load** (the role gate).

| Field | Requirement |
|---|---|
| **root node** | exactly one node with `parent_id: null`; carries `properties.corpus_schema_version = "1"`; is a fork (`role: branch`) and carries **no** `menu_label` (the root is never a menu option) |
| `properties.role` (every node) | ∈ `{branch, answer, bottom, procedure}` — unknown/missing → refused |
| `properties.menu_label` (**every non-root node**) | the text the enumerator shows when this node appears as a menu option. Required on **every** selectable node — branch, answer, bottom, and procedure alike — so the enumerator never invents a label. Missing on a non-root node → refused |
| **`branch`** | a fork: `menu_label` is its subtree prompt; children listed via `contains` |
| **`answer`** | a leaf: `properties.answer_text` is delivered **verbatim**; the provenance address is the node-id path from root |
| **`bottom`** | the authored ⊥ floor (the no-answer route): `menu_label` + `answer_text`, flagged `role: bottom`. **At least one _unprotected_ bottom node MUST be a direct child of the root** (`root_bottom`) so the retry-exhaustion chain always terminates at a floor **every session can reach** (deeper bottoms may be `protected`; the root floor may not) |
| **`procedure`** | **reserved, never executed in V1** (out of scope). The loader accepts it, the enumerator lists it, the executor refuses it (fail-honest ⊥ shape). V2 provisioning |
| `properties.protected` | optional bool: marks a capability-gated subtree — the enumerator excludes it for sessions lacking the capability. **Orthogonal to `role`, not a role value** |
| `edges` | optional cross-links; the V1 walk follows `contains` only — edges are advisory metadata |

## ⊥ routing & gap kind

On `RETRY BOUNDED 1` exhaustion (a backend that returns an off-menu id twice), the
engine routes to the **nearest-ancestor bottom** — the bottom child of the deepest
ancestor of the current cursor that has one **and that the session may access**
(a `protected` bottom the session lacks is skipped), falling back to the mandatory
unprotected `root_bottom`. The delivered answer's provenance address is the bottom's own
root→node path. The written gap record's `kind` is:

- **`deep-⊥`** — a non-root bottom absorbed the miss, or
- **`root-⊥`** — the `root_bottom` did.

Because `root_bottom` is a loader requirement, the routing chain is **total**: no corpus
can present the engine a menu with no reachable ⊥.

## Minimal example

```json
{
  "name": "faq", "version": "1.0.0", "type": "PROJECT", "dimension": "system",
  "dimensions": { "system": { "description": "demo" } },
  "nodes": [
    { "id": "root", "type": "CONCEPT", "parent_id": null, "contains": ["about", "none"],
      "metric_level": "BASE_TOPIC", "dimension": "system",
      "properties": { "role": "branch", "corpus_schema_version": "1" } },
    { "id": "about", "type": "CONCEPT", "parent_id": "root", "contains": [],
      "metric_level": "BASE_TOPIC", "dimension": "system",
      "properties": { "role": "answer", "menu_label": "What is TRUGS?",
                      "answer_text": "TRUGS is a constrained, executable subset of English." } },
    { "id": "none", "type": "CONCEPT", "parent_id": "root", "contains": [],
      "metric_level": "BASE_TOPIC", "dimension": "system",
      "properties": { "role": "bottom", "menu_label": "None of these / not sure",
                      "answer_text": "No authored answer covers that yet." } }
  ],
  "edges": []
}
```
