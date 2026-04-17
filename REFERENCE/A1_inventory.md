# A1 — Noise Chatbot Go Surface Inventory

**Issue:** #1555 — Phase A, step A1
**Source commit:** `TRUGS-LLC/noise-chatbot` @ read-only clone, inventoried 2026-04-17
**Source tree:** `~/REPO/noise-chatbot/` (local clone — no edits)
**Output format:** flat enumeration, no analysis. Phase A2 translates each row to TRL.

## Scope

Catalog the full observable surface of the Go implementation across **6 packages** (`noise`, `protocol`, `server`, `client`, `helper`, `examples/*`). Enumerate:

1. Exported functions, types, methods, interfaces, vars
2. CLI subcommands + flags
3. HTTP routes + request/response shape
4. Goroutine / channel boundaries (concurrency model)
5. Persistence operations (filesystem, network, in-memory state)
6. External dependencies
7. Error types + wrapping pattern

No CLI config files (no cobra/viper — only one binary with one `flag` package use).

## LOC by File (non-vendor)

| File | LOC |
|---|---:|
| `noise/noise.go` | 50 |
| `noise/conn.go` | 85 |
| `noise/frame.go` | 37 |
| `noise/client.go` | 68 |
| `noise/server.go` | 92 |
| `noise/noise_test.go` | 310 |
| `protocol/message.go` | 17 |
| `protocol/message_test.go` | 52 |
| `server/server.go` | 935 |
| `server/server_test.go` | 814 |
| `client/client.go` | 88 |
| `client/client_test.go` | 94 |
| `helper/main.go` | 96 |
| `examples/echo/main.go` | 17 |
| `examples/faq/main.go` | 39 |
| `examples/llm/main.go` | 20 |
| `examples/graph/main.go` | 18 |
| **total** | **2832** |

Non-test prod LOC: **1562**. Test LOC: **1270**.

## External Dependencies (`go.mod`)

| Import | Version | Use |
|---|---|---|
| `github.com/flynn/noise` | v1.1.0 | Noise_IK handshake + CipherState primitives |
| `github.com/google/uuid` | v1.6.0 | Message ID generation (server) |
| `golang.org/x/crypto` | v0.0.0-20210322153248-0c34fe9e7dc2 | indirect (via flynn/noise) |
| `golang.org/x/sys` | v0.0.0-20201119102817-f84b799fce68 | indirect |

Go version: `go 1.24.0`.

Stdlib imports used: `bufio`, `context`, `crypto/rand`, `encoding/binary`, `encoding/hex`, `encoding/json`, `errors` (none — all wrapping via `fmt.Errorf`), `flag`, `fmt`, `io`, `log`, `net`, `os`, `os/signal`, `strings`, `sync`, `syscall`, `time`.

---

## Package `noise`

**Path:** `noise/`
**TRL header (from source):** `MODULE noise IMPLEMENTS INTERFACE encrypted_transport. MODULE noise CONTAINS FUNCTION GenerateKeypair AND FUNCTION Dial AND FUNCTION Listen.`
**Role:** Noise_IK TCP transport (handshake + length-prefixed framed encryption).

### Exports — `noise.go`

| Kind | Name | Signature | Notes |
|---|---|---|---|
| type alias | `DHKey` | `= noiselib.DHKey` | Re-exports `flynn/noise` static keypair type |
| var | `CipherSuite` | `noiselib.CipherSuite` | `NewCipherSuite(DH25519, CipherChaChaPoly, HashBLAKE2b)` — fixed suite, no negotiation |
| func | `GenerateKeypair` | `() (noiselib.DHKey, error)` | Reads `crypto/rand.Reader` for entropy |
| func | `KeyToHex` | `(key []byte) string` | `hex.EncodeToString` |
| func | `HexToKey` | `(s string) ([]byte, error)` | Validates 32-byte length |

### Exports — `conn.go`

| Kind | Name | Signature | Notes |
|---|---|---|---|
| type | `NoiseConn` | `struct { conn net.Conn; encrypt, decrypt *noiselib.CipherState; remote []byte; mu, rmu sync.Mutex }` | All fields unexported; remote = peer's static pubkey |
| method | `(*NoiseConn).Send` | `(msg []byte) error` | Thread-safe (holds `mu`); encrypts, writes 4-byte big-endian length prefix, then ciphertext |
| method | `(*NoiseConn).Receive` | `() ([]byte, error)` | Thread-safe (holds `rmu`); 16MB max ciphertext cap — closes conn on violation |
| method | `(*NoiseConn).Close` | `() error` | Delegates to `conn.Close()` |
| method | `(*NoiseConn).RemoteIdentity` | `() []byte` | Returns peer static public key |

**Framing:** 4-byte `binary.BigEndian` uint32 length prefix + ciphertext. Max frame 16 MiB. Decrypt failure closes the connection (no recovery).

### Exports — `frame.go` (unexported helpers)

| Kind | Name | Signature | Notes |
|---|---|---|---|
| func | `writeFrame` | `(conn net.Conn, data []byte) error` | 4-byte big-endian prefix for handshake frames |
| func | `readFrame` | `(conn net.Conn) ([]byte, error)` | 65 536-byte cap for handshake (smaller than data frame cap) |

### Exports — `client.go`

| Kind | Name | Signature | Notes |
|---|---|---|---|
| func | `Dial` | `(addr string, clientKey DHKey, serverPubKey []byte) (*NoiseConn, error)` | TCP dial + `ClientHandshake`; closes conn on failure |
| func | `ClientHandshake` | `(conn net.Conn, clientKey DHKey, serverPubKey []byte) (*NoiseConn, error)` | Noise_IK initiator. Pattern `-> e, es, s, ss` / `<- e, ee, se`. 1-RTT (2 frames). |

### Exports — `server.go`

| Kind | Name | Signature | Notes |
|---|---|---|---|
| type | `Listener` | `struct { inner net.Listener; serverKey DHKey }` | Wraps `net.Listener` |
| func | `Listen` | `(addr string, serverKey DHKey) (*Listener, error)` | TCP listen |
| method | `(*Listener).Accept` | `() (*NoiseConn, error)` | Blocks, accepts, runs `ServerHandshake`; closes raw conn on handshake failure |
| method | `(*Listener).Close` | `() error` | |
| method | `(*Listener).Addr` | `() net.Addr` | |
| func | `ServerHandshake` | `(conn net.Conn, serverKey DHKey) (*NoiseConn, error)` | Noise_IK responder. Reads msg1, writes msg2. Extracts client static pubkey via `hs.PeerStatic()`. |

### Error strings — `noise`

All errors wrap via `fmt.Errorf("...: %w", err)`. No named error types. Format strings:

- `"invalid hex key: %w"`, `"key must be 32 bytes, got %d"`
- `"noise encrypt: %w"`, `"noise send length: %w"`, `"noise send: %w"`
- `"noise recv length: %w"`, `"noise recv: message too large (%d bytes)"`, `"noise recv: %w"`, `"noise decrypt: %w"`
- `"write frame length: %w"`, `"write frame data: %w"`, `"read frame length: %w"`, `"frame too large: %d bytes"`, `"read frame data: %w"`
- `"dial: %w"`, `"listen: %w"`, `"accept: %w"`
- `"handshake init: %w"`, `"handshake write msg1: %w"`, `"handshake send msg1: %w"`, `"handshake recv msg2: %w"`, `"handshake read msg2: %w"`
- `"handshake recv msg1: %w"`, `"handshake read msg1: %w"`, `"handshake write msg2: %w"`, `"handshake send msg2: %w"`

### Concurrency — `noise`

- `NoiseConn.mu` — guards `Send` (serialises writes).
- `NoiseConn.rmu` — guards `Receive` (serialises reads). Separate from write mutex so concurrent read + write is permitted.
- No goroutines spawned inside the package. Goroutines are spawned by callers (`server` package, `helper` binary).

### Persistence — `noise`

- None. All state in-memory. No filesystem, no DB.
- Network: TCP `net.Dial` / `net.Listen`.

---

## Package `protocol`

**Path:** `protocol/`
**TRL header:** `MODULE protocol CONTAINS RECORD Message.`
**Role:** Wire envelope type (JSON).

### Exports — `message.go`

| Kind | Name | Signature | Notes |
|---|---|---|---|
| type | `Message` | `struct { Type string; Payload json.RawMessage; ID string; ReplyTo string }` | JSON tags `type`, `payload`, `id`, `reply_to,omitempty` |

No functions, no methods. Pure data record.

**Known `Type` values** (observed in `server` and `client`): `"CHAT"`, `"ERROR"`. Arbitrary types permitted by the schema (default echo branch in `handleMessageFull`).
**Payload shapes** (observed):
- `CHAT`: `{"text": string}`
- `ERROR`: `{"error": string}`

---

## Package `server`

**Path:** `server/`
**TRL header:** `MODULE server CONTAINS FUNCTION New AND FUNCTION ListenAndServe AND FUNCTION OnChat AND FUNCTION WithResponses AND FUNCTION WithGuardrails. EACH RECORD message FROM ENTRY client SHALL ROUTE TO FUNCTION handleMessageFull.`
**Role:** Chatbot server. Template-mode (LLM classifies → pre-authored node text returned verbatim) or legacy handler mode. Safety + honeypot + wind-down.

### Types

| Kind | Name | Shape | Notes |
|---|---|---|---|
| struct | `ResponseNode` | `{ID, Keywords []string, Response string}` | JSON tags `id`, `keywords`, `response` |
| func type | `Classifier` | `func(userText string, nodes []ResponseNode) []string` | Returns matched node IDs, ordered by relevance. Never returns text. |
| func type | `ChatHandler` | `func(text string) string` | DEPRECATED — legacy free-text |
| func type | `MessageHandler` | `func(msg protocol.Message) protocol.Message` | Full-message callback |
| struct | `SafetyConfig` | `{MaxInputTokens, MaxInputBytes, RateLimit int; SessionTimeout time.Duration; Greeting string; ConfidenceMin int}` | All fields exported; 0 = unlimited |
| struct | `ConnectionStats` | `{MessagesReceived int; NodeHits map[string]int; NoMatchCount int; ConnectedAt, LastMessageAt time.Time}` | Per-connection |
| struct | `Server` | see below | All fields unexported |
| struct | `LLMConfig` | `{Provider, Model, APIKeyEnv string}` | Values: `"anthropic"`, `"openai"` for `Provider` |

**`Server` unexported fields:** `addr string`, `key noise.DHKey`, `chatHandler ChatHandler`, `msgHandler MessageHandler`, `trugData map[string]any`, `llmConfig *LLMConfig`, `upstreamAddr, upstreamKey string`, `responses []ResponseNode`, `guardrails []ResponseNode`, `classifier Classifier`, `fallbackClassifier Classifier`, `noMatchText string`, `safety SafetyConfig`, `bannedKeys map[string]time.Time`, `bannedMu sync.RWMutex`, `contactFooter string`, `onAnalytics func(ConnectionStats, string, []string)`.

### Vars

| Kind | Name | Content | Notes |
|---|---|---|---|
| var | `DefaultGuardrails` | `[]ResponseNode` of length **15** | IDs: `guard-identity`, `guard-creator`, `guard-admin`, `guard-password`, `guard-apikey`, `guard-prompt`, `guard-inject`, `guard-personal`, `guard-others`, `guard-harmful`, `guard-offtopic`, `guard-distress`, `guard-capabilities`, `guard-language`, `guard-feedback`. Exact keyword lists and response text are in `server/server.go:116-132`. |

### Funcs

| Kind | Name | Signature | Notes |
|---|---|---|---|
| func | `New` | `(addr string) *Server` | Auto-generates keypair via `noise.GenerateKeypair()`. Defaults: `MaxInputTokens=200`, `MaxInputBytes=2000`, `RateLimit=30/min`, `SessionTimeout=30m`, `ConfidenceMin=1`, `noMatchText="I don't have information about that. Please contact us directly."`, `guardrails = copy(DefaultGuardrails)`. |

### Methods (all return `*Server` — builder pattern, chainable)

| Method | Signature | Behaviour |
|---|---|---|
| `WithSafety` | `(cfg SafetyConfig) *Server` | Overwrites full safety config |
| `WithGreeting` | `(text string) *Server` | Sets `safety.Greeting`; first message sent on connect |
| `WithGuardrails` | `(path string) *Server` | Reads file, JSON-unmarshals TRUG, appends each node with a non-empty `response` property (along with its `keywords[]`) to the guardrails list. Logs warning on read failure; silent on parse failure. Logs "Loaded N guardrail nodes from PATH". |
| `OnAnalytics` | `(fn func(ConnectionStats, string, []string)) *Server` | Called for every message: `(stats, userText, matchedNodeIDs)` |
| `WithResponses` | `(nodes []ResponseNode) *Server` | Replaces response list |
| `WithResponsesFromTRUG` | `(path string) *Server` | Reads `.trug.json`. Extracts per node: `properties.response` (fallback `properties.description`), `properties.keywords[]`, `properties.name` (appended as keyword). Skips nodes with no response text. Logs warning on read/parse failure. Logs "Loaded N response nodes from PATH". |
| `WithClassifier` | `(Classifier) *Server` | Overrides default keyword classifier |
| `WithFallbackClassifier` | `(Classifier) *Server` | LLM-backed fallback, only invoked when keyword classifier returns nil **and** `questionCount <= 20` |
| `WithNoMatch` | `(text string) *Server` | Overrides no-match text |
| `WithContactFooter` | `(footer string) *Server` | Appended to every response after a blank line |
| `OnChat` | `(ChatHandler) *Server` | DEPRECATED legacy free-text mode |
| `OnMessage` | `(MessageHandler) *Server` | Full message callback — takes priority over all other routing |
| `WithTRUG` | `(path string) *Server` | Loads a `.trug.json` as read-only chatbot context (available via `GetTRUGContext`) |
| `WithLLM` | `(provider, model, apiKeyEnv string) *Server` | Stores `LLMConfig`; does not wire classifier (user must call `WithClassifier` separately) |
| `WithUpstream` | `(addr, key string) *Server` | Gateway mode to TRUGS_PORT (fields stored but not actioned in server.go) |
| `Key` | `() noise.DHKey` | Full keypair (tests) |
| `PublicKey` | `() string` | `KeyToHex(key.Public)` |
| `GetTRUGContext` | `() string` | Returns a text summary of loaded TRUG data (format: "Knowledge base:\n- NAME: DESC\n...") |
| `GetResponses` | `() []ResponseNode` | Returns the loaded response-node list |

### Lifecycle methods

| Method | Signature | Behaviour |
|---|---|---|
| `ListenAndServe` | `() error` | Calls `noise.Listen(addr, key)`; installs `signal.Notify` for `SIGINT`/`SIGTERM` via a 1-capacity channel; spawns a signal goroutine that cancels the root context and closes the listener on signal; `accept` loop spawns `go serveConn(ctx, conn)` per accepted connection. Returns nil on clean shutdown, wrapped error on listen failure. |
| `ServeListener` | `(ctx context.Context, listener *noise.Listener) error` | Same accept loop without its own signal handler; closes listener when ctx is cancelled. Used by tests. |

### Unexported functions / methods

| Kind | Name | Signature | Behaviour |
|---|---|---|---|
| func | `defaultClassifier` | `(userText string, nodes []ResponseNode) []string` | Case-insensitive substring matching. Each keyword hit in a node adds 1 to score. Nodes with score > 0 returned, sorted by score descending. Returns nil on no match. |
| method | `(*Server).buildTRUGContext` | `() string` | Walks `trugData["nodes"]` array, emits `"- NAME: DESC\n"` for each node with a non-empty name. |
| method | `(*Server).serveConn` | `(ctx context.Context, conn *noise.NoiseConn)` | Per-connection goroutine body. See "Behaviour" block below. |
| method | `(*Server).handleMessage` | `(msg protocol.Message) protocol.Message` | Legacy test helper — delegates to `handleMessageFull(msg, 0)`. |
| method | `(*Server).handleMessageWithStats` | `(msg protocol.Message) (protocol.Message, []string, bool)` | Identical delegation. |
| method | `(*Server).handleMessageFull` | `(msg protocol.Message, questionCount int) (protocol.Message, []string, bool)` | Returns `(response, matchedNodeIDs, hitGuardrail)`. See "Message routing" below. |
| func | `mustMarshalJSON` | `(v any) json.RawMessage` | Swallows errors. |

### Behaviour — `serveConn`

1. Lookup `keyHex = KeyToHex(RemoteIdentity())` in `bannedKeys` (under `bannedMu.RLock`).
   - If banned and (ban-time is zero [permanent] **or** `time.Since(banTime) < 72h`) → silent close.
   - Otherwise remove ban and continue.
2. Initialise `ConnectionStats{NodeHits: map, ConnectedAt: now}`; locals `guardrailHits`, `questionCount`, per-conn `rateMu` + `messageTimestamps`.
3. If `safety.Greeting != ""` → send a `CHAT` message with greeting, new UUID id, no ReplyTo.
4. Loop:
   1. Check `ctx.Err()`; return if cancelled.
   2. Check session-idle timeout: if `LastMessageAt != zero` and `time.Since(LastMessageAt) > safety.SessionTimeout` → return.
   3. `conn.Receive()` — return on error.
   4. Input-size byte limit: if `len(data) > MaxInputBytes` → reply `ERROR{"message too large"}`, continue.
   5. Rate limit: maintain a sliding 1-minute window in `messageTimestamps`; if over `RateLimit` → reply `ERROR{"rate limit exceeded, please slow down"}`, continue.
   6. Increment `MessagesReceived`, set `LastMessageAt = now`.
   7. `json.Unmarshal(data, &msg)` — continue silently on parse failure.
   8. Approx token limit: if `msg.Type == "CHAT"` and `len(req.Text)/4 > MaxInputTokens` → reply `CHAT{"Please keep your message shorter — I work best with concise questions."}`, continue.
   9. Call `resp, matchedNodes, hitGuardrail = handleMessageFull(msg, questionCount)`.
   10. Record analytics: increment `NodeHits[id]` for each matched ID; if `len(matched)==0` increment `NoMatchCount`.
   11. If `msg.Type == "CHAT"` → `questionCount++`.
   12. **Wind-down** (only if `msg.Type == "CHAT"` and `!hitGuardrail`):
       - `questionCount >= 20` → `time.Sleep((questionCount-20) * 5s)`.
       - `questionCount == 20` → replace `resp` with a "We've covered a lot! Here's what we discussed: {topics}. You can find more detail on all of these on our website. I'm still here if you have more questions!" summary built from `ConnectionStats.NodeHits` (topic = first keyword of each hit node).
       - `questionCount >= 40` → send farewell CHAT (`"Thank you for chatting with us today! I hope I was able to help. For anything else, please visit our website or contact our team directly. Have a great day!"`), register `bannedKeys[keyHex] = now` (3-day temporary ban), log `"Temp-banned key XXXX for 3 days (40 questions reached)"`, return.
   13. **Honeypot** (independent of wind-down):
       - `hitGuardrail` → `guardrailHits++`.
       - `guardrailHits >= 3` → sleep 3s (tier 2), 8s (≥5, tier 3), or 15s (≥8, tier 4).
       - `>= 12` → tier 5 farewell CHAT (`"Thank you for chatting with us today! It looks like I've answered everything I can. Have a great day!"`), `bannedKeys[keyHex] = now` **but** the server treats zero-time as permanent; note: code stores `time.Now()`, so eventual expiry is 72h. Logged `"Banned key XXXX (honeypot tier 5 — repeated probing)"`. Return.
       - Between tiers 2-4, `resp` is replaced by one of 4/3/3 canned honeypot CHAT strings (see `server.go:750-788`), cycled via `guardrailHits % len(pool)`.
   14. Call `onAnalytics(stats, userText, matchedNodes)` if set.
   15. `conn.Send(json.Marshal(resp))`; return on send error.

### Behaviour — `handleMessageFull`

1. If `msgHandler != nil` → return `msgHandler(msg), nil, false` (full override; skips all CHAT logic).
2. If `msg.Type == "CHAT"`:
   1. Unmarshal `msg.Payload` as `{text: string}`.
   2. `classify = s.classifier`; if nil, use `defaultClassifier`.
   3. Run `classify(text, guardrails)`; if any match, `hitGuardrail = true`, take first node's `Response` verbatim.
   4. Otherwise, if `len(responses) > 0`:
      - `nodeIDs = classify(text, responses)`.
      - If `nodeIDs` empty **and** `fallbackClassifier != nil` **and** `questionCount <= 20` → retry with fallback.
      - Cap `nodeIDs` at 3.
      - If still empty → `responseText = noMatchText`.
      - Else concatenate matched nodes' `Response` text with `"\n\n"`.
   5. Otherwise if `chatHandler != nil` → `responseText = chatHandler(text)` (DEPRECATED path).
   6. Otherwise echo `text`.
   7. Formatting: if `questionCount > 0` → prepend `"You asked about: {text}\n\n"`; if `contactFooter != ""` → append `"\n\n{footer}"`; if `questionCount > 0` → append `"\n\n({questionCount})"`.
   8. Build `CHAT` response with new UUID, `ReplyTo = msg.ID`.
3. Non-CHAT → echo: same Type, same Payload, new UUID, `ReplyTo = msg.ID`.

### Concurrency — `server`

**Goroutines:**
| Site | Spawn | Lifecycle |
|---|---|---|
| `ListenAndServe` | `go func() { <-sigCh; cancel(); listener.Close() }()` | Fires once on first SIGINT/SIGTERM. |
| `ServeListener` | `go func() { <-ctx.Done(); listener.Close() }()` | Fires when caller cancels ctx. |
| accept loop | `go s.serveConn(ctx, conn)` | One per accepted Noise connection; runs until recv error, ctx cancel, session timeout, or honeypot/wind-down ban. |

**Channels:**
| Name | Type | Capacity | Use |
|---|---|---|---|
| `sigCh` | `chan os.Signal` | 1 | `signal.Notify(sigCh, SIGINT, SIGTERM)` in `ListenAndServe` |
| (ctx) | `context.Context` | — | Root cancellation for shutdown + per-conn cancellation |

**Mutexes:**
| Name | Type | Guards |
|---|---|---|
| `Server.bannedMu` | `sync.RWMutex` | `Server.bannedKeys map[string]time.Time` |
| (per-conn) `rateMu` | `sync.Mutex` | `messageTimestamps []time.Time` (sliding 1-min window) |

### Persistence — `server`

- `os.ReadFile(path)` in `WithGuardrails`, `WithResponsesFromTRUG`, `WithTRUG`. JSON-unmarshal only.
- No disk writes. No database. No network outbound except TCP listener.
- In-memory state:
  - `bannedKeys map[string]time.Time` — stored value: `time.Now()` on ban, `time.Time{}` (zero) never actually written (all paths use `time.Now()`). Permanent-ban semantics exist in code (`banTime.IsZero()` branch) but no caller sets zero-time — every real ban expires after 72 h.
  - `messageTimestamps` — per-conn, pruned to last minute on each message.
  - `trugData`, `responses`, `guardrails` — loaded once via builder.

### External deps — `server`

| Import | Use |
|---|---|
| `github.com/TRUGS-LLC/noise-chatbot/noise` | Transport |
| `github.com/TRUGS-LLC/noise-chatbot/protocol` | Message envelope |
| `github.com/google/uuid` | `uuid.New().String()` for response IDs |

### Error strings — `server`

Wrapped: `"listen: %w"` (ListenAndServe).
Log-only (does not propagate): `"warning: could not load TRUG %s: %v"`, `"warning: could not load guardrails %s: %v"`, `"warning: could not parse TRUG %s: %v"`, `"Loaded %d guardrail nodes from %s"`, `"Loaded %d response nodes from %s"`, `"Noise Chatbot listening on %s"`, `"Public key: %s"`, `"Template mode: %d response nodes loaded (LLM classifies, never composes)"`, `"shutting down..."`, `"accept error: %v"`, `"Temp-banned key %s for 3 days (40 questions reached)"`, `"Banned key %s (honeypot tier 5 — repeated probing)"`.

Over-the-wire (Message payloads with `Type="ERROR"` or `Type="CHAT"`): `"message too large"`, `"rate limit exceeded, please slow down"`, `"Please keep your message shorter — I work best with concise questions."`.

---

## Package `client`

**Path:** `client/`
**TRL header:** `MODULE client CONTAINS FUNCTION Connect AND FUNCTION Chat AND FUNCTION Send AND FUNCTION Close. FUNCTION Connect SHALL AUTHENTICATE SUBJECT_TO RECORD server_public_key.`
**Role:** Go client library.

### Exports

| Kind | Name | Signature | Notes |
|---|---|---|---|
| type | `Client` | `struct { conn *noise.NoiseConn }` | Field unexported |
| func | `Connect` | `(addr, serverPublicKeyHex string) (*Client, error)` | Decodes hex, generates ephemeral static keypair (per connection), dials |
| method | `(*Client).Chat` | `(text string) (string, error)` | Builds CHAT message with `ID = "msg-<unix-nano>"`, unmarshals response `{text}` field |
| method | `(*Client).Send` | `(msg protocol.Message) (protocol.Message, error)` | Marshals, sends, receives, unmarshals full message |
| method | `(*Client).Close` | `()` | No error return |

### Error strings — `client`

Wrapped: `"invalid server key: %w"`, `"keygen: %w"`, `"connect: %w"`, `"marshal: %w"`, `"send: %w"`, `"receive: %w"`, `"unmarshal: %w"`.

### Concurrency — `client`

No goroutines. Synchronous request/response via `NoiseConn.Send` then `NoiseConn.Receive`. `NoiseConn` mutexes make calls safe across goroutines but library itself spawns none.

### Persistence — `client`

None. In-memory only.

### External deps — `client`

`github.com/TRUGS-LLC/noise-chatbot/noise`, `github.com/TRUGS-LLC/noise-chatbot/protocol`. No third-party.

---

## Binary `helper/noise-helper`

**Path:** `helper/main.go`
**Role:** stdin/stdout Noise_IK bridge for non-Go clients.
**Build:** `go build -o noise-helper ./helper`.

### CLI flags (`flag` package)

| Flag | Type | Default | Required | Meaning |
|---|---|---|---|---|
| `--server` | string | `localhost:9090` | no | `host:port` of Noise server |
| `--key` | string | `""` | **yes** | Server public key (hex) |

Exits with `os.Exit(1)` to stderr with `"ERROR: --key required"` if missing.

### stdout / stderr protocol

- On handshake success, prints `"CONNECTED\n"` to stdout.
- Per received server message: writes raw decrypted bytes + `"\n"` to stdout (caller guaranteed JSON).
- On recv error (server-side disconnect): `fmt.Fprintf(os.Stderr, "ERROR: recv: %v\n")`, `os.Exit(0)` — treats EOF as clean exit.
- On send error: `fmt.Fprintf(os.Stderr, "ERROR: send: %v\n")`, `os.Exit(1)`.
- On stdin non-JSON line: `fmt.Fprintf(os.Stderr, "ERROR: invalid JSON on stdin\n")`, continues (does not exit).

### stdin contract

- `bufio.Scanner` with 16 MiB buffer (`scanner.Buffer(16*1024*1024, 16*1024*1024)`).
- One JSON message per line. Empty lines skipped.
- Each line validated via `json.Valid(line)` before sending.
- Scanner ends → process returns cleanly.

### Concurrency — `helper`

| Goroutine | Body |
|---|---|
| main | stdin scan → `conn.Send` |
| reader | `for { data, err := conn.Receive(); os.Stdout.Write(data); ... }` — exits process on error |

No channels. No mutexes (reader writes to stdout directly; stdlib serialises writes to the same file descriptor at OS level).

### Persistence — `helper`

None. Pure pipe bridge.

### External deps — `helper`

stdlib + `github.com/TRUGS-LLC/noise-chatbot/noise`.

---

## Examples

All examples are `package main` binaries under `examples/*/`. None take CLI flags. All listen on `:9090`.

| Example | LOC | External input | Handler |
|---|---:|---|---|
| `echo` | 17 | none | `OnChat(text => "You said: " + text)` |
| `faq` | 39 | `faq.json` (cwd) — `map[string]string` Q→A | keyword `strings.Contains` match (case-insensitive); fallback `"I don't have an answer for that. Try asking about: {keys}"` |
| `llm` | 20 | `ANTHROPIC_API_KEY` env | stubbed: `"LLM integration coming soon. You asked: {text}"` — configured via `WithLLM("anthropic", "claude-haiku-4-5", "ANTHROPIC_API_KEY")` but classifier not wired |
| `graph` | 18 | `knowledge.trug.json` (cwd) — loaded via `WithTRUG` | stubbed: `"Graph-backed response coming soon. You asked: {text}"` |

Note: `faq` uses a helper `joinKeys(map[string]string) string`. No goroutines. No persistence writes. Prints public key on startup.

---

## HTTP Routes

**NONE.** Noise Chatbot is TCP-only (Noise_IK transport). The framework does not use `net/http`. The README comparison table mentions "HTTP/TLS Chatbot" as a contrast, not an implementation. No HTTP handlers, no `http.ServeMux`, no routes. Port conventionally `:9090` but fully configurable.

---

## Persistence Summary

| Operation | Where | Direction | Format |
|---|---|---|---|
| `os.ReadFile(path)` — guardrails TRUG | `server.WithGuardrails` | read | JSON TRUG |
| `os.ReadFile(path)` — responses TRUG | `server.WithResponsesFromTRUG` | read | JSON TRUG |
| `os.ReadFile(path)` — context TRUG | `server.WithTRUG` | read | JSON TRUG |
| `os.ReadFile("faq.json")` | `examples/faq` | read | JSON `map[string]string` |
| Stdin line scan | `helper` | read | JSON lines |
| Stdout line write | `helper` | write | JSON lines |
| TCP listen / accept | `noise.Listen`, `server.ListenAndServe` | bidirectional | Noise_IK framed |
| TCP dial | `noise.Dial`, `client.Connect`, `helper.main` | bidirectional | Noise_IK framed |
| `log.Printf` | stdlib log → stderr | write | text |

No database. No HTTP. No file writes (except stdout in helper). No `os.Setenv`; reads env only for the LLM example pattern (`LLMConfig.APIKeyEnv`).

---

## Goroutine / Channel Boundaries — Full Inventory

| Process | Goroutines | Channels | Mutexes |
|---|---|---|---|
| `noise` library | 0 | 0 | per-`NoiseConn`: `mu` (Send), `rmu` (Receive) |
| `protocol` library | 0 | 0 | 0 |
| `client` library | 0 | 0 | — (inherits from NoiseConn) |
| `server.ListenAndServe` | 1 signal goroutine + N connection goroutines (one per accept) | 1 signal `chan os.Signal` (cap 1), `context.Context` | `Server.bannedMu` (RWMutex), per-conn `rateMu` (Mutex), per-conn NoiseConn `mu`/`rmu` |
| `server.ServeListener` | 1 ctx-close goroutine + N connection goroutines | `context.Context` | same as above |
| `helper` binary | 1 main + 1 reader | 0 | 0 |

**Back-pressure:** There is no explicit back-pressure. Each connection goroutine serialises its own send/receive. The server's accept loop has no bound — under load it spawns one goroutine per connection without limit. Rate limiting is per-connection only, not global.

**Ordering:** Per-connection message ordering is guaranteed (single goroutine, sync request/response). Across connections no ordering guarantees. Wind-down and honeypot counters are per-connection locals, not shared.

---

## Error Patterns — Repo-wide

- No custom error types (no `type XError struct{}`, no `errors.New` sentinels, no `var ErrFoo = ...`).
- All errors produced via `fmt.Errorf("context: %w", innerErr)` or bare `fmt.Errorf("context: %d bytes", n)` for validation failures.
- Log calls via stdlib `log.Printf` (no structured logger, no leveled logger).
- `client` + `helper` + `server` all rely on `NoiseConn.Receive` returning `io.EOF`-equivalent to mean disconnect; `helper` translates this to `os.Exit(0)`, `server.serveConn` to clean `return`.
- Over-the-wire errors are `protocol.Message{Type: "ERROR", Payload: {"error": "..."}}`, sent in-band on the same connection.

---

## Symbol Counts (for A3 function-node validation)

| Package | Exported funcs / methods | Exported types | Exported vars | Total public symbols |
|---|---:|---:|---:|---:|
| `noise` | 10 (`GenerateKeypair`, `KeyToHex`, `HexToKey`, `Dial`, `ClientHandshake`, `Listen`, `ServerHandshake`, plus `NoiseConn.{Send,Receive,Close,RemoteIdentity}` and `Listener.{Accept,Close,Addr}`) | 3 (`DHKey`, `NoiseConn`, `Listener`) | 1 (`CipherSuite`) | 14 |
| `protocol` | 0 | 1 (`Message`) | 0 | 1 |
| `server` | 22 (`New` + 19 `With*/On*` builders + `Key` + `PublicKey` + `GetTRUGContext` + `GetResponses` + `ListenAndServe` + `ServeListener`) | 8 (`ResponseNode`, `Classifier`, `ChatHandler`, `MessageHandler`, `SafetyConfig`, `ConnectionStats`, `Server`, `LLMConfig`) | 1 (`DefaultGuardrails`) | 31 |
| `client` | 4 (`Connect`, `Client.Chat`, `Client.Send`, `Client.Close`) | 1 (`Client`) | 0 | 5 |
| `helper` | — binary — `main()` only | — | — | — |
| `examples/*` | — binaries — `main()` only | — | — | — |
| **totals (library)** | **36** | **13** | **2** | **51** |

**A3 validation target:** super-TRUG must contain one `FUNCTION` node per exported func/method in the library packages (36 nodes). Types map to `RECORD` nodes (13 nodes). Vars map to `RESOURCE` nodes (2 nodes). CLI surface = 1 `INTERFACE` node (noise-helper with 2 flags) + 4 `STAGE` nodes (example binaries). TCP listener = 1 `SERVICE` node (Server). Transport = 1 `SERVICE` node (Noise_IK).

---

## Test coverage (observed, for A4 parity corpus scope)

Tests are not part of the exported surface but reveal behaviour contracts to be preserved in parity corpus.

| File | Tests | Selected names |
|---|---:|---|
| `noise/noise_test.go` | 8 | `TestGenerateKeypair`, `TestKeyHexRoundTrip`, `TestNoiseRoundTrip`, `TestNoiseWrongKey`, `TestNoiseEncryption`, `TestServerMultipleClients`, `TestHelperCompiles`, `TestFrameTooLarge` |
| `protocol/message_test.go` | 2 | `TestMessageJSON`, `TestMessageOmitEmptyReplyTo` |
| `client/client_test.go` | 3 | `TestClientConnect`, `TestClientChat`, `TestClientSendMessage` |
| `server/server_test.go` | 22 | `TestServerOnChat`, `TestServerEcho`, `TestServerGracefulShutdown`, `TestServerMultipleClients`, `TestGetTRUGContext`, `TestTemplateMode{Single,Multiple,No,Overrides,CustomClassifier}Match`, `TestLLMNeverGeneratesText`, `TestGuardrailsMatchFirst`, `TestHoneypotResponseChanges`, `TestBannedKeyRejected`, `TestWindDown20Summary`, `TestWindDown40Goodbye`, `TestRateLimit`, `TestInputSizeLimit`, `TestGreeting`, `TestMatchCap3`, `TestFallbackClassifier`, `TestContactFooter` |
| **total** | **35** | |

---

## Open questions surfaced during A1 (parked for A2/A3)

Flat enumeration only — these are observations, not decisions. Take them to A2 translation.

1. **`Server.bannedKeys` permanent-ban semantics.** Code branches on `banTime.IsZero()` to mean "permanent", but no call site stores a zero time. Is permanent ban a dead-code path, or a future feature? Parity fixture needed: temp-ban (72h) vs permanent-ban expected behaviour.
2. **Test helper `handleMessageWithStats` is identical to `handleMessage(msg, 0)`.** Both exist but neither threads `questionCount`. Suggests an interface evolution in progress. For the TRUG, collapse to `handleMessageFull(msg, questionCount)` and flag the other two as thin wrappers.
3. **`WithLLM` stores config but does not install a classifier.** Caller must pair it with `WithClassifier` or `WithFallbackClassifier`. Document in A2 sentence.
4. **`WithUpstream` stores `upstreamAddr` / `upstreamKey` but `server.go` never references them.** Feature stub for gateway mode. Track as `[STUB]` or `[DEFERRED]` in A3 and future Python impl.
5. **Wind-down sleep is per-message, not cumulative.** After question N (N>=20), sleep = `(N-20)*5s`. So question 25 waits 25s, question 30 waits 50s. Concretise in A4 fixtures.
6. **Honeypot tier response pool cycling uses `guardrailHits % pool_len`** — so tier 2 cycles 3 messages, tier 3 cycles 3, tier 4 cycles 4. Two separate tier-transition boundaries (3→5→8→12) must be expressed.
7. **Match cap of 3** is hard-coded; no builder exposes it.
8. **Token approximation** (`len/4`) is hard-coded; configurable only via `MaxInputTokens = 0` (unlimited).
9. **Per-connection rate-window** uses slice scan + realloc (`filtered := messageTimestamps[:0]`). Semantics: sliding 1-minute window, event budget = `RateLimit`. Python impl may prefer `collections.deque`.
10. **Default guardrails are compiled-in** (`DefaultGuardrails` in `server.go:116-132`) **and** also shipped as `guardrails.trug.json`. These are two sources of truth for the same 15 entries. A3 must pick one as canonical — likely the compiled-in list (code) with the JSON as a consumer-editable mirror.

---

**End of A1 inventory.** Next: A2 per-symbol TRL sentences (`A2_trl_sentences.md`).
