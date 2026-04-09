# Noise Chatbot

An encrypted chatbot framework where every message is end-to-end encrypted using the Noise Protocol (Curve25519 + ChaCha20-Poly1305).

## Quickstart

```go
package main

import (
    "fmt"
    "github.com/TRUGS-LLC/noise-chatbot/server"
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
go get github.com/TRUGS-LLC/noise-chatbot
```

## Examples

### Echo Bot

The simplest chatbot -- echoes back whatever you say.

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
import "github.com/TRUGS-LLC/noise-chatbot/client"

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
noise-chatbot/
  noise/       Noise_IK transport (Curve25519 + ChaCha20-Poly1305)
  protocol/    Message type (JSON wire format)
  server/      New(), OnChat(), WithTRUG(), WithLLM(), ListenAndServe()
  client/      Connect(), Chat(), Send(), Close()
  helper/      noise-helper stdin/stdout bridge
  examples/    echo, faq, llm, graph
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

- `type` -- message type (CHAT for text, or custom types)
- `payload` -- arbitrary JSON payload
- `id` -- unique message identifier
- `reply_to` -- optional, links response to request

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.

Built on the [Noise Protocol Framework](https://noiseprotocol.org/) using [flynn/noise](https://github.com/flynn/noise) (BSD License).
