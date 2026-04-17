# noise-chatbot-go

> **Successor notice (2026-04-17):** the **actively-developed** version of this project is the Python rewrite at **[`TRUGS-LLC/noise-chatbot`](https://github.com/TRUGS-LLC/noise-chatbot)** (Apache 2.0). This Go repo (`Xepayac/noise-chatbot-go`) is the **reference implementation** — behaviourally pinned by `REFERENCE/parity/`, relicensed to **AGPL-3.0**.
>
> If you're integrating Noise Chatbot into a product, use the Python package. If you need the Go implementation under AGPL terms, you're in the right place.

An encrypted chatbot framework where every message is end-to-end encrypted using the Noise Protocol (Curve25519 + ChaCha20-Poly1305).

## Quickstart

```go
package main

import (
    "fmt"
    "github.com/Xepayac/noise-chatbot-go/server"
)

func main() {
    s := server.New(":9090")
    s.OnChat(func(text string) string {
        return "You said: " + text
    })
    fmt.Println("Public key:", s.PublicKey())
    s.ListenAndServe()
}
```

That's it. Every message is encrypted. No TLS certificates. No configuration.

> **Import-path note:** the old module path `github.com/TRUGS-LLC/noise-chatbot` still resolves via GitHub's redirect, but new code should import `github.com/Xepayac/noise-chatbot-go`. A `go.mod` update to match the new path will follow.

## Why Noise Chatbot?

|  | Noise Chatbot | HTTP/TLS Chatbot | Plain TCP |
|--|---------------|------------------|-----------|
| Encryption | Noise_IK (Curve25519 + ChaCha20-Poly1305) | TLS 1.3 (certificate required) | None |
| Setup | `server.New(":9090")` | Certificate + key + config | `net.Listen()` |
| Identity | Public key (64 hex chars) | X.509 certificate chain | None |
| Auth model | Know the key = trusted | CA-signed certificate | None |
| Forward secrecy | Yes (ephemeral DH per session) | Yes (with TLS 1.3) | No |
| Dependencies | 1 (flynn/noise) | stdlib | stdlib |

**Noise_IK** means the client knows the server's public key before connecting. No certificate authorities. No DNS. No MITM window. The handshake is 1-RTT and authenticates both sides.

## Install

```bash
# New path:
go get github.com/Xepayac/noise-chatbot-go

# Old path (redirects — works but deprecated):
# go get github.com/TRUGS-LLC/noise-chatbot
```

## Examples

### Echo Bot

The simplest chatbot — echoes back whatever you say.

```bash
go run ./examples/echo
```

### FAQ Bot

Loads answers from a JSON file and matches keywords.

```bash
cd examples/faq && go run .
```

### LLM Bot

Connects to an LLM provider (Anthropic, OpenAI) for AI-powered responses.

```bash
export ANTHROPIC_API_KEY=sk-...
go run ./examples/llm
```

### Graph Bot

Loads a `.trug.json` knowledge graph as chatbot context.

```bash
cd examples/graph && go run .
```

## Client

### Go Client

```go
import "github.com/Xepayac/noise-chatbot-go/client"

c, err := client.Connect(":9090", serverPublicKeyHex)
if err != nil { log.Fatal(err) }
defer c.Close()

response, err := c.Chat("Hello!")
fmt.Println(response) // "You said: Hello!"
```

### noise-helper (stdin/stdout bridge)

For non-Go clients, `noise-helper` bridges stdin/stdout over an encrypted Noise connection:

```bash
go build -o noise-helper ./helper
./noise-helper --server localhost:9090 --key <server-public-key-hex>
# Prints "CONNECTED" on success
# Then: JSON lines on stdin -> encrypted -> server
#        server -> decrypted -> JSON lines on stdout
```

Wire format (JSON lines):
```json
{"type":"CHAT","payload":{"text":"Hello!"},"id":"msg-1"}
```

## Architecture

```
Client                          Server
  |                               |
  |  Noise_IK Handshake (1-RTT)  |
  |------------------------------>|
  |<------------------------------|
  |                               |
  |  Encrypted JSON Messages      |
  |<=============================>|  --> OnChat(func)
  |                               |  --> OnMessage(func)
  |                               |  --> WithTRUG(path)
  |                               |  --> WithLLM(provider)
```

```
noise-chatbot-go/
  noise/       Noise_IK transport (Curve25519 + ChaCha20-Poly1305)
  protocol/    Message type (JSON wire format)
  server/      New(), OnChat(), WithTRUG(), WithLLM(), ListenAndServe()
  client/      Connect(), Chat(), Send(), Close()
  helper/      noise-helper stdin/stdout bridge
  examples/    echo, faq, llm, graph
  REFERENCE/   Phase-A TRUG-driven rewrite pedigree — super-TRUG,
               TRL sentences, behaviour-parity YAML corpus. The same
               corpus validates both this Go implementation and the
               Python successor.
```

## Message Format

All communication uses a simple JSON envelope:

```json
{
    "type": "CHAT",
    "payload": {"text": "Hello!"},
    "id": "msg-123",
    "reply_to": "msg-122"
}
```

- `type` — message type (CHAT for text, or custom types)
- `payload` — arbitrary JSON payload
- `id` — unique message identifier
- `reply_to` — optional, links response to request

## Relationship to the Python successor

The Python rewrite at [`TRUGS-LLC/noise-chatbot`](https://github.com/TRUGS-LLC/noise-chatbot) was regenerated from [`REFERENCE/noise_chatbot.super.trug.json`](REFERENCE/noise_chatbot.super.trug.json) without reading this Go source. The same 17-fixture behaviour-parity corpus at [`REFERENCE/parity/`](REFERENCE/parity/) validates both implementations. See [`REFERENCE/LAB_1555_noise_chatbot_rewrite.md`](REFERENCE/LAB_1555_noise_chatbot_rewrite.md) for the full methodology write-up.

## License

**GNU Affero General Public License v3.0 (AGPL-3.0-only).** See [LICENSE](LICENSE) and [NOTICE](NOTICE) for details.

Previously Apache License 2.0 under `TRUGS-LLC/noise-chatbot`; relicense authority is documented in [`NOTICE`](NOTICE) and [TRUGS-DEVELOPMENT#1550](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/1550).

Built on the [Noise Protocol Framework](https://noiseprotocol.org/) using [flynn/noise](https://github.com/flynn/noise) (BSD License).
