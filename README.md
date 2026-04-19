# noise-chatbot (Python)

Encrypted chatbot framework over Noise_IK (Curve25519 + ChaCha20-Poly1305 + BLAKE2b).

Python reimplementation of [`TRUGS-LLC/noise-chatbot`](https://github.com/TRUGS-LLC/noise-chatbot) (Go), generated from [`noise_chatbot.super.trug.json`](https://github.com/Xepayac/TRUGS-DEVELOPMENT/blob/main/REFERENCE/noise_chatbot.super.trug.json) per the TRUG-driven rewrite methodology.

**Status:** Phase B scaffold. Function bodies are `NotImplementedError` stubs. Phase C fills them from the super-TRUG without reading Go source.

## Quickstart (future — after Phase C)

```python
from noise_chatbot.server import Server

s = Server(":9090")
s.on_chat(lambda text: "You said: " + text)
print("Public key:", s.public_key())
s.listen_and_serve()
```

## Why Python

Same reasons as the Go original — encrypted end-to-end chatbot with no TLS certificates, no DNS, no MITM window — plus:

- Drop-in replacement for Python teams already on the Python-AI ecosystem.
- **Pluggable stores.** Guardrails, responses, banned keys, and the TRUG knowledge base each live behind a tiny `Protocol`. Ship with the zero-dependency in-memory / JSON-file defaults, or opt in to the graph-backed [`trugs-store`](https://github.com/TRUGS-LLC/TRUGS-STORE) adapter for persistent state. See [Stores](#stores) below.
- Apache 2.0 (matching the Go original's license pre-#1550-relicense).

## Install

```bash
pip install noise-chatbot          # standalone — in-memory + JSON-file stores
pip install noise-chatbot[trugs]   # + trugs-store graph adapter
```

From source during development:

```bash
git clone https://github.com/TRUGS-LLC/noise-chatbot
cd noise-chatbot
pip install -e ".[dev]"            # includes trugs-store for the full test suite
```

## Stores

The `Server` holds four kinds of swappable persistent-state:

| Protocol | What it does | In-memory default | JSON-file | `[trugs]` extra |
|---|---|---|---|---|
| `GuardrailStore` | Pre-authored boundary responses | compiled-in 15 nodes | — | `TrugsGuardrailStore` |
| `ResponseStore` | Classifier match targets | empty list | `JsonFileResponseStore(path)` | `TrugsResponseStore` |
| `BannedKeyStore` | TTL-bounded bans (slowdown, not prevention) | `InMemoryBannedKeyStore(ttl=72h)` | `JsonFileBannedKeyStore(path, ttl)` | `TrugsBannedKeyStore` |
| `KnowledgeBaseStore` | TRUG context injection | empty | `JsonFileKnowledgeBaseStore(path)` | `TrugsKnowledgeBaseStore` |

Wire one in via the builder API:

```python
from datetime import timedelta
from noise_chatbot.server import Server
from noise_chatbot.stores import JsonFileBannedKeyStore, JsonFileResponseStore

s = (
    Server(":9090")
    .with_response_store(JsonFileResponseStore("responses.trug.json"))
    .with_banned_keys(JsonFileBannedKeyStore("bans.json", ttl=timedelta(hours=72)))
)
```

Or the legacy path-based shortcuts (preserved — they now wrap the stores internally):

```python
s = Server(":9090").with_responses_from_trug("responses.trug.json")
```

### Opting in to trugs-store

```python
# pip install noise-chatbot[trugs]
from trugs_store import JsonFilePersistence
from noise_chatbot.stores.trugs import TrugsBannedKeyStore

graph = JsonFilePersistence().load("chatbot.trug.json")
s = Server(":9090").with_banned_keys(TrugsBannedKeyStore(graph))
# The graph is mutated in place — caller is responsible for persisting via
# JsonFilePersistence.save() or the postgres backend before shutdown.
```

Every `BannedKeyStore` implementation is **required** (by the Protocol's type signature) to enforce `ttl: timedelta` expiry. No permanent-ban implementation is possible — bans are a slowdown mechanism, not prevention.

## Architecture

```
noise_chatbot/
  noise/       Noise_IK transport (Curve25519 + ChaCha20-Poly1305)
  protocol/    Message type (JSON wire format)
  server/      Server, SafetyConfig, ResponseNode, DEFAULT_GUARDRAILS
  client/      Client, connect, chat, send, close
  helper/      noise-helper stdin/stdout bridge
  examples/    echo, faq, llm, graph
```

The Python API mirrors the Go API with idiomatic Python naming (snake_case instead of PascalCase for methods; Python dataclasses instead of Go structs). Behavioural parity is enforced by the parity corpus under `tests/parity/`.

## Testing

```bash
pytest                    # unit + integration
pytest -m parity          # Go-golden parity corpus (needs Go binaries)
ruff check . && ruff format --check . && mypy src tests
```

## Parity

Phase A of [issue #1555 in TRUGS-DEVELOPMENT](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1555) produced a 21-fixture YAML corpus that the Go implementation passes. This Python implementation is validated against the same corpus — Phase C is complete when all 17 runnable fixtures pass.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Built on:
- The [Noise Protocol Framework](https://noiseprotocol.org/)
- [`noiseprotocol`](https://github.com/plizonczyk/noiseprotocol) (BSD 3-Clause)
- [`trugs-store`](https://github.com/TRUGS-LLC/TRUGS-STORE) — optional, via the `[trugs]` extra
