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
- First-class `trugs-store` integration for TRUG-shaped persistent state.
- Apache 2.0 (matching the Go original's license pre-#1550-relicense).

## Install

```bash
pip install noise-chatbot  # (not yet on PyPI — Phase E)
```

From source during development:

```bash
git clone https://github.com/TRUGS-LLC/noise-chatbot
cd noise-chatbot
pip install -e ".[dev]"
```

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
- [`trugs-store`](https://github.com/TRUGS-LLC/trugs-store) for graph persistence
