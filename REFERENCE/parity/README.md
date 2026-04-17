# Behavior-Parity Test Corpus

Phase A4 deliverable for #1555 — the Go-golden test corpus that validates
the Python rewrite against the reference Go implementation.

## What this is

A fixture-driven test suite that exercises the Go `noise-chatbot` server
through the **real wire protocol** (Noise_IK over TCP) and asserts the
observed responses match documented expectations. Every fixture:

1. Starts a configured Go server instance via the harness binary.
2. Connects as a client using the `noise-helper` bridge.
3. Sends JSON messages, captures decrypted JSON responses.
4. Asserts match.

Because the fixtures speak JSON over stdin/stdout of real binaries, they
are language-agnostic. Phase C will replay the same fixtures against the
Python reimplementation — if the Python impl produces matching output,
behavioural parity is demonstrated.

## Status — 2026-04-17

| Category | Count |
|---|---:|
| Fixtures total | 21 |
| Runnable | 17 |
| Passing against Go golden | **17 / 17** ✅ |
| Intentionally skipped | 4 (documented with `skip: true`) |

### Runnable coverage by function

| Fixture | Function under test |
|---|---|
| 01_echo_basic | `(*Server).OnChat` |
| 02_template_single_match | `(*Server).WithResponses` + `defaultClassifier` |
| 03_template_no_match | `(*Server).WithNoMatch` |
| 04_template_multi_match | `handleMessageFull` (concat with `\n\n`) |
| 05_template_match_cap_3 | `handleMessageFull` (hard cap at 3) |
| 06_guardrail_hit_identity | `DefaultGuardrails` |
| 07_contact_footer | `(*Server).WithContactFooter` |
| 08_greeting_first_message | `(*Server).WithGreeting` |
| 09_input_byte_limit | `(*Server).WithSafety` (`MaxInputBytes`) |
| 10_input_token_limit | `(*Server).WithSafety` (`MaxInputTokens`) |
| 11_non_chat_echoes | `handleMessageFull` (fall-through) |
| 12_reply_to_roundtrip | `protocol.Message` (JSON roundtrip) |
| 13_template_overrides_onchat | `handleMessageFull` (override precedence) |
| 14_classifier_case_insensitive | `defaultClassifier` |
| 15_custom_guardrail_appended | `(*Server).WithGuardrails` (additive) |
| 17_session_timeout_short | `(*Server).WithSafety` (`SessionTimeout`) |
| 21_question_count_format | `handleMessageFull` (N≥1 formatting wrap) |

### Skipped fixtures (with reasons)

| Fixture | Reason |
|---|---|
| 16_helper_missing_key | CLI-only; no server/session. Verified manually; automated exec belongs in a separate helper-process runner. |
| 18_rate_limit_DEFERRED | Tight-loop case runnable; window-slide needs 60s wall time. |
| 19_wind_down_40_ban_DEFERRED | ~17.5 minutes wall time to reach questionCount=40 under production delay schedule. |
| 20_honeypot_tier_DEFERRED | ~105s cumulative tier delays. Partial (tier-2 only) feasible at ~5s. |

All skipped fixtures are implementable without harness changes; they are
not blockers to Phase A validation.

## Running the corpus

### Prerequisites

1. Go 1.24+ installed and `$GOPATH/bin` on `PATH`.
2. Python 3.8+ with `pyyaml`: `pip install pyyaml`.
3. Local clone of `TRUGS-LLC/noise-chatbot` (used as source for the
   harness binary build).

### Build the binaries

```bash
# Copy the harness source into a noise-chatbot checkout, then build.
cd ~/REPO/noise-chatbot
mkdir -p tests/parity/harness
cp /path/to/REFERENCE/parity/harness/main.go tests/parity/harness/main.go
go build -o /tmp/parity-harness ./tests/parity/harness
go build -o /tmp/noise-helper   ./helper
```

### Run all fixtures

```bash
cd /path/to/REFERENCE/parity
python3 runner.py \
    --harness /tmp/parity-harness \
    --helper  /tmp/noise-helper \
    fixtures/*.yaml
```

Expected output (current state):

```
[PASS] 01_echo_basic.yaml: echo_basic
[PASS] 02_template_single_match.yaml: template_single_match
...
17/21 passed (0 failed, 4 skipped)
```

### Run a single fixture

```bash
python3 runner.py --harness ... --helper ... fixtures/06_guardrail_hit_identity.yaml
```

## Architecture

```
┌────────────────────────────────────────────────────┐
│ runner.py (Python)                                 │
│                                                    │
│ 1. parse YAML fixture                              │
│ 2. spawn parity-harness with fixture.harness JSON  │
│ 3. read "READY host:port pubkey"                   │
│ 4. spawn noise-helper --server ... --key ...       │
│ 5. read "CONNECTED"                                │
│ 6. for each interaction: stdin JSON → stdout JSON  │
│ 7. compare against fixture.expect                  │
└────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    parity-harness ◄══ Noise_IK TCP ══► noise-helper
    (Go server wrapped    (real Noise        (stdin/stdout
     in a configurable     handshake +        bridge from
     fixture shim)         encryption)        Go code)
```

The harness binary is a thin wrapper around `server.Server` that reads a
JSON config on stdin — responses, safety settings, greeting, footer,
handler mode, etc. — and starts a configured instance on an ephemeral
port. Everything the runner sends traverses the real Noise transport.

The runner uses `noise-helper` (the production-shipped CLI) as the test
client. This has two important properties:
1. Any deviation in `noise-helper`'s wire behaviour shows up as a fixture
   failure.
2. Fixtures are language-agnostic — a future Python implementation of
   the server runs under the same fixtures without modifying anything.

## Fixture format

```yaml
name:        <short id>
package:     server | noise | protocol | client | helper
function:    <Go symbol name>
description: <prose explanation>
trl: |
  <TRL sentence asserting the invariant under test>

harness:                  # JSON-serialised to stdin of parity-harness
  chat_handler: echo      # or "prefix" with prefix_text, or omit
  responses:              # []server.ResponseNode
    - id: ...
      keywords: [...]
      response: ...
  extra_guardrails: [...] # appended to DefaultGuardrails
  no_match_text: ...
  greeting: ...
  contact_footer: ...
  max_input_tokens: N     # 0 = use default (200)
  max_input_bytes:  N     # 0 = use default (2000)
  rate_limit:       N     # 0 = use default (30)
  session_timeout_seconds: N
  raw_safety: bool        # true = zero-value fields mean unlimited

interactions:
  - send:                 # JSON Message; this is what the client sends
      type: CHAT
      payload: {text: "hello"}
      id: msg-1
    expect:               # assertions on the decoded response
      type: CHAT
      payload_text: "hello"          # substring match
      payload_text_exact: "You said: hello"  # exact match
      error_payload: "rate limit..." # exact match on payload.error
      payload_equals: {foo: "bar"}   # exact payload object match
      reply_to: msg-1
      timeout_seconds: 5.0
      expect_no_response: false
  - expect_only: true     # consume next push (e.g. server greeting)
    expect: {...}
  - delay_seconds: 2      # sleep before next interaction

skip: true                # optional — skip this fixture
skip_reason: |
  <why>
```

## Known limitations (A4 v1)

1. **DefaultGuardrails can't be cleared.** The harness has no access to
   the unexported `guardrails` field on `Server`. Fixtures that assert
   business-response behavior must phrase user text carefully to avoid
   any of the 15 compiled-in guardrail keywords. Documented per fixture.
2. **Time-dependent fixtures (rate-limit window slide, wind-down
   sleep, honeypot tier delays) are deferred.** Each requires either
   real wall-clock waiting or a test-only seam in the Go code that
   mocks `time.Sleep`/`time.Now`. Neither is added in v1.
3. **No fallback-classifier fixture.** Exercising `WithFallbackClassifier`
   requires either an in-process Go classifier or an HTTP stub for the
   LLM. Deferred.
4. **No upstream-gateway fixture.** `WithUpstream` stores fields that
   `server.go` never reads — flagged in A1/A2 as `[STUB]`.

## Follow-ups for v1.1

- Short-window rate-limit fixture (tight loop, no window slide needed).
- Tier-2 honeypot delay fixture (~5s cumulative, hits 3-4).
- Helper CLI fixtures (run `noise-helper` subprocess directly).
- Multi-connection isolation fixture (two helpers to one harness; assert
  per-conn state is not shared).
- Encryption invariant fixture: capture ciphertext bytes at the TCP
  layer and assert they differ from plaintext (the Go TestNoiseEncryption
  test does this in-process; mirror externally via a packet sniffer or
  a tee proxy).

## Relationship to the super-TRUG

Every fixture's `trl:` block should be derivable from the A2 TRL
sentence corpus and the corresponding node in
[noise_chatbot.super.trug.json](../noise_chatbot.super.trug.json). When
Phase C generates Python code from the super-TRUG, these fixtures are
the acceptance criteria.
