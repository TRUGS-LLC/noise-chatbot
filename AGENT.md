# noise-chatbot — Agent Guide

<trl>
DEFINE "noise_chatbot" AS NAMESPACE.
NAMESPACE noise_chatbot CONTAINS MODULE server AND MODULE client AND MODULE noise
    AND MODULE protocol AND MODULE helper AND MODULE examples.
MODULE server IMPLEMENTS INTERFACE chatbot_server.
INTERFACE chatbot_server GOVERNS ALL RECORD Message FROM ENTRY client TO EXIT response.
</trl>

## What this repo is

A Python reimplementation of [`TRUGS-LLC/noise-chatbot`](https://github.com/TRUGS-LLC/noise-chatbot) (Go), regenerated from [`noise_chatbot.super.trug.json`](https://github.com/Xepayac/TRUGS-DEVELOPMENT/blob/main/REFERENCE/noise_chatbot.super.trug.json). The super-TRUG is the spec; this codebase is the implementation; the behaviour-parity corpus is the acceptance criteria.

**Phase B (current):** scaffold — modules, types, contracts, `NotImplementedError` stubs.
**Phase C:** implementation from super-TRUG (no reading Go source).

## Navigation

| Package | What It Does | Go parity |
|---|---|---|
| `src/noise_chatbot/noise/` | Noise_IK transport — handshake, encryption, framing | `noise/` |
| `src/noise_chatbot/protocol/` | Wire format — `Message` type | `protocol/` |
| `src/noise_chatbot/server/` | Chatbot server — `Server`, safety, guardrails, honeypot | `server/` |
| `src/noise_chatbot/client/` | Client library — `connect`, `chat`, `send`, `close` | `client/` |
| `src/noise_chatbot/helper/` | `noise-helper` stdin/stdout bridge binary | `helper/` |
| `src/noise_chatbot/examples/` | `echo`, `faq`, `llm`, `graph` | `examples/` |
| `tests/unit/` | Fast, isolated unit tests | N/A (covered by `_test.go`) |
| `tests/integration/` | Real-transport integration | `server_test.go` |
| `tests/parity/` | Go-golden fixtures from TRUGS-DEVELOPMENT#1555 | same YAML files |

## Key design rule

<trl>
AGENT SHALL_NOT WRITE ANY RECORD response 'that 'is NOT FROM RECORD ResponseNode.
FUNCTION classifier SHALL RETURNS_TO MODULE server RECORD node_id.
FUNCTION classifier SHALL_NOT RETURNS_TO MODULE server RECORD text.
SERVICE Server SHALL READ RECORD response FROM RECORD ResponseNode
    THEN SEND RESULT TO ENTRY client.
</trl>

The LLM classifies — picks node IDs from the TRUG. It NEVER composes response text. Every word the user sees was written by a human and stored in a `ResponseNode`.

## Hard rules for agents

<trl>
AGENT SHALL READ FILE noise_chatbot.super.trug.json 'before IMPLEMENT ANY FUNCTION.
AGENT SHALL_NOT READ ANY FILE 'from RESOURCE go_source 'during STAGE coding.
AGENT SHALL VALIDATE EACH FUNCTION SUBJECT_TO DATA parity_corpus.
</trl>

- **Super-TRUG is the spec.** During Phase C, the super-TRUG + this repo's scaffold + parity fixtures are the only inputs. The Go source is NOT a reference — if you need to "check how Go does X," fix the super-TRUG instead.
- **Every `<trl>` block is a contract.** If the implementation doesn't match its `<trl>`, the `<trl>` is wrong or the implementation is wrong — reconcile before committing.
- **Parity fixtures are acceptance.** Phase C is complete when all 17 runnable parity fixtures pass.

## Build + test + check

```bash
pip install -e ".[dev]"        # install + dev deps
ruff format --check .           # formatting
ruff check .                    # linting
mypy src tests                  # type checking
pytest                          # test suite
pytest --cov=noise_chatbot      # with coverage
```

Single-command all-gates run (Layer-1 Dark Code check):

```bash
ruff format --check . && ruff check . && mypy src tests && pytest
```

## Parity harness

The parity corpus at `tests/parity/` is the same set of YAML fixtures used against the Go golden in Phase A4 ([TRUGS-DEVELOPMENT#1563](https://github.com/Xepayac/TRUGS-DEVELOPMENT/pull/1563)). To run against the Python implementation:

```bash
# Once Phase C installs the helper entry point:
pip install -e ".[dev]"
python -m noise_chatbot.tests.parity.runner tests/parity/fixtures/*.yaml
```

## Relationship to Go repo

The Go repo `TRUGS-LLC/noise-chatbot` will be moved to `Xepayac/noise-chatbot-go` under AGPL-3.0 before this Python repo ships (Phase D, [TRUGS-DEVELOPMENT#1550](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1550)). This Python repo takes the `TRUGS-LLC/noise-chatbot` name under Apache 2.0.

Parity fixtures travel with the Go code to the AGPL fork — anyone can run them against either implementation and get the same JSON responses for the same JSON inputs.
