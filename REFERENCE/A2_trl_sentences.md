# A2 — Noise Chatbot TRL Per-Symbol Sentences

**Issue:** #1555 — Phase A, step A2
**Input:** [`A1_inventory.md`](A1_inventory.md) — 51 library public symbols + helper CLI + 4 examples
**Method:** Paper §3 Step B — one plain-English sentence, one TRL sentence per symbol. [VOCAB-GAP] markers flag concepts the 190-word vocabulary cannot express cleanly; these become A3 node-properties or TRUGS spec issues, not local inventions.
**TRL vocabulary source:** `CLAUDE.md` §"TRUGS Language (TRL) — 190-Word Vocabulary".

## Convention

Each row is:
- **Name** — the Go symbol
- **English** — one plain-English sentence stating what it does
- **TRL** — one TRL sentence using only the 190-word vocabulary
- **Gap** — `—` or `[VOCAB-GAP: …]` if a concept resists translation

All TRL subject actors must be one of `PARTY | AGENT | PROCESS | SERVICE | FUNCTION | TRANSFORM | PRINCIPAL` (modals require actor subjects). Data-shaped things use `DATA | RECORD | MESSAGE | STREAM | FILE | RESOURCE`. Sugar words (`OF, IS, THAT, WITH, FOR, AT, ON, INTO, UPON, …`) are included for readability and compile to nothing.

---

## Package `noise`

### Module header

**TRL:**
`MODULE noise IMPLEMENTS INTERFACE encrypted_transport. MODULE noise CONTAINS FUNCTION GenerateKeypair AND FUNCTION Dial AND FUNCTION Listen.`

### Symbols

| Name | English | TRL | Gap |
|---|---|---|---|
| `DHKey` (type alias) | A Curve25519 static keypair (public + private). | `DEFINE RECORD DHKey CONTAINS STRING public AND STRING private.` | — |
| `CipherSuite` (var) | The fixed cipher suite for all connections: Curve25519 + ChaCha20-Poly1305 + BLAKE2b. | `DEFINE RESOURCE CipherSuite AS IMMUTABLE DATA CONTAINS DH25519 AND ChaChaPoly AND BLAKE2b.` | — |
| `GenerateKeypair()` | Generate a new Curve25519 static keypair using secure random entropy. | `FUNCTION GenerateKeypair SHALL READ DATA FROM RESOURCE rand THEN DEFINE A RECORD DHKey THEN RETURNS_TO SOURCE.` | — |
| `KeyToHex(key)` | Encode a byte slice as a hexadecimal string. | `FUNCTION KeyToHex SHALL MAP DATA key AS STRING hex THEN RETURNS_TO SOURCE.` | — |
| `HexToKey(s)` | Decode a hex string to a 32-byte key; reject invalid hex or wrong length. | `FUNCTION HexToKey SHALL VALIDATE STRING s THEN REJECT IF STRING s 'is INVALID OR NOT EQUALS 32. FUNCTION HexToKey SHALL MAP STRING s AS DATA key THEN RETURNS_TO SOURCE.` | — |
| `NoiseConn` (type) | An encrypted connection: wraps a TCP connection with two CipherStates and remembers the peer's public key. | `DEFINE RECORD NoiseConn CONTAINS RESOURCE conn AND DATA encrypt AND DATA decrypt AND STRING remote.` | [VOCAB-GAP: `sync.Mutex` fields `mu`/`rmu` — no TRL word for a lock primitive; encode as property `concurrency_safe: true` on the node in A3.] |
| `(*NoiseConn).Send(msg)` | Encrypt a message and write it with a 4-byte big-endian length prefix; thread-safe. | `FUNCTION Send SHALL MAP DATA msg AS DATA ciphertext BY DATA encrypt THEN WRITE INTEGER length AND DATA ciphertext TO RESOURCE conn. FUNCTION Send SHALL_NOT SEND ANY DATA msg IN PARALLEL 'with SELF.` | [VOCAB-GAP: "length-prefix framing" — encoded as two sequential WRITE ops; specific uint32 big-endian encoding captured in node property `frame_format: "uint32_be_length_prefix"`.] |
| `(*NoiseConn).Receive()` | Read a length-prefixed ciphertext, decrypt it, reject frames over 16 MiB, close on decrypt failure; thread-safe. | `FUNCTION Receive SHALL READ INTEGER length FROM RESOURCE conn THEN REJECT IF INTEGER length EXCEEDS 16777216. FUNCTION Receive SHALL READ DATA ciphertext FROM RESOURCE conn THEN MAP DATA ciphertext AS DATA plaintext BY DATA decrypt. FUNCTION Receive SHALL THROW EXCEPTION THEN CATCH EXCEPTION THEN REVOKE RESOURCE conn IF DATA decrypt FAILED.` | — |
| `(*NoiseConn).Close()` | Close the underlying TCP connection. | `FUNCTION Close SHALL REVOKE RESOURCE conn.` | — |
| `(*NoiseConn).RemoteIdentity()` | Return the peer's static public key bytes. | `FUNCTION RemoteIdentity SHALL RETURNS_TO SOURCE STRING remote.` | — |
| `writeFrame(conn, data)` (unexp) | Write a length-prefixed frame to a connection. | `FUNCTION writeFrame SHALL WRITE INTEGER length AND DATA data TO RESOURCE conn.` | — |
| `readFrame(conn)` (unexp) | Read a length-prefixed frame (65 536-byte cap) from a connection. | `FUNCTION readFrame SHALL READ INTEGER length FROM RESOURCE conn THEN REJECT IF INTEGER length EXCEEDS 65536. FUNCTION readFrame SHALL READ DATA data FROM RESOURCE conn THEN RETURNS_TO SOURCE.` | — |
| `Dial(addr, clientKey, serverPubKey)` | TCP-dial a server and perform the Noise_IK client handshake; close on failure. | `FUNCTION Dial SHALL REQUEST RESOURCE conn FROM ENDPOINT addr THEN AUTHENTICATE RECORD clientKey SUBJECT_TO STRING serverPubKey BY FUNCTION ClientHandshake. FUNCTION Dial SHALL REVOKE RESOURCE conn IF FUNCTION ClientHandshake 'is FAILED.` | — |
| `ClientHandshake(conn, clientKey, serverPubKey)` | Noise_IK initiator: send `e, es, s, ss`; read `e, ee, se`; produce a NoiseConn. | `FUNCTION ClientHandshake SHALL DEFINE DATA handshake AS INITIATOR SUBJECT_TO STRING serverPubKey. FUNCTION ClientHandshake SHALL WRITE DATA msg1 TO RESOURCE conn THEN READ DATA msg2 FROM RESOURCE conn THEN RETURNS_TO SOURCE RECORD NoiseConn.` | [VOCAB-GAP: "Noise_IK pattern (-> e, es, s, ss / <- e, ee, se)" — the cryptographic message flow names are domain jargon; encode literal pattern string as node property `noise_pattern: "IK"`.] |
| `Listener` (type) | A TCP listener paired with the server's static key; each Accept yields a Noise handshake. | `DEFINE RECORD Listener CONTAINS RESOURCE inner AND RECORD serverKey.` | — |
| `Listen(addr, serverKey)` | Start a TCP listener on `addr` bound to the server key. | `FUNCTION Listen SHALL DEFINE RESOURCE Listener AT ENDPOINT addr BINDS RECORD serverKey THEN RETURNS_TO SOURCE.` | — |
| `(*Listener).Accept()` | Block until a client connects, run the responder handshake, close raw conn on handshake failure. | `FUNCTION Accept SHALL RECEIVE RESOURCE conn FROM RESOURCE Listener THEN AUTHENTICATE PARTY client BY FUNCTION ServerHandshake. FUNCTION Accept SHALL REVOKE RESOURCE conn IF FUNCTION ServerHandshake 'is FAILED.` | — |
| `(*Listener).Close()` | Close the TCP listener. | `FUNCTION Close SHALL REVOKE RESOURCE Listener.` | — |
| `(*Listener).Addr()` | Return the listening address. | `FUNCTION Addr SHALL RETURNS_TO SOURCE ENDPOINT addr.` | — |
| `ServerHandshake(conn, serverKey)` | Noise_IK responder: read `e, es, s, ss`; write `e, ee, se`; extract client's static public key. | `FUNCTION ServerHandshake SHALL DEFINE DATA handshake AS RESPONDER BINDS RECORD serverKey. FUNCTION ServerHandshake SHALL READ DATA msg1 FROM RESOURCE conn THEN WRITE DATA msg2 TO RESOURCE conn THEN MAP DATA handshake AS STRING clientPub THEN RETURNS_TO SOURCE RECORD NoiseConn.` | [VOCAB-GAP: same IK pattern jargon as ClientHandshake.] |

### Error conventions

| Pattern | TRL |
|---|---|
| `fmt.Errorf("context: %w", err)` (all errors) | `FUNCTION ANY IN MODULE noise SHALL THROW EXCEPTION 'that CONTAINS STRING context AND RECORD inner.` |
| 16 MiB frame cap / 65 536 handshake cap | `FUNCTION Receive SHALL REJECT DATA ciphertext IF INTEGER length EXCEEDS 16777216. FUNCTION readFrame SHALL REJECT DATA data IF INTEGER length EXCEEDS 65536.` |
| Decrypt failure closes conn | `FUNCTION Receive SHALL REVOKE RESOURCE conn IF DATA decrypt 'is FAILED.` |

---

## Package `protocol`

### Module header

**TRL:**
`MODULE protocol CONTAINS RECORD Message.`

### Symbols

| Name | English | TRL | Gap |
|---|---|---|---|
| `Message` (type) | The JSON envelope for every wire message: type, payload, id, and optional reply_to. | `DEFINE RECORD Message CONTAINS STRING type AND DATA payload AND STRING id AND OPTIONAL STRING reply_to.` | — |
| `Type` known values | `"CHAT"` and `"ERROR"` are the two known type values; any other type echoes. | `EACH RECORD Message SHALL MATCH STRING type AS STRING CHAT OR STRING ERROR OR ANY STRING.` | — |
| `Payload` shapes | CHAT carries `{text}`; ERROR carries `{error}`. | `EACH RECORD Message WITH STRING type EQUALS CHAT SHALL CONTAIN STRING text. EACH RECORD Message WITH STRING type EQUALS ERROR SHALL CONTAIN STRING error.` | — |

---

## Package `server`

### Module header

**TRL:**
`MODULE server CONTAINS FUNCTION New AND FUNCTION ListenAndServe AND FUNCTION OnChat AND FUNCTION WithResponses AND FUNCTION WithGuardrails. MODULE server DEPENDS_ON MODULE noise AND MODULE protocol. EACH RECORD Message FROM ENTRY client SHALL ROUTE TO FUNCTION handleMessageFull.`

### Types

| Name | English | TRL | Gap |
|---|---|---|---|
| `ResponseNode` | A pre-authored response: ID, keywords, verbatim response text. | `DEFINE RECORD ResponseNode CONTAINS STRING id AND ARRAY keywords AND STRING response.` | — |
| `Classifier` (func type) | Picks matching ResponseNode IDs from user text; returns IDs only, never text. | `DEFINE FUNCTION Classifier SHALL MAP STRING userText AND ARRAY nodes AS ARRAY ids. FUNCTION Classifier SHALL_NOT WRITE ANY STRING text.` | — |
| `ChatHandler` (func type, DEPRECATED) | Legacy callback returning arbitrary text given input text. | `DEFINE FUNCTION ChatHandler SHALL MAP STRING text AS STRING response. AGENT claude SHALL DEPRECATE FUNCTION ChatHandler.` | [VOCAB-GAP: "deprecated" — closest is SHALL_NOT MAY (retire). Encode as property `deprecated: true`.] |
| `MessageHandler` (func type) | Full message-in, message-out callback. | `DEFINE FUNCTION MessageHandler SHALL MAP RECORD Message AS RECORD Message.` | — |
| `SafetyConfig` | Per-server safety knobs: input-token cap, input-byte cap, rate limit, session timeout, greeting, confidence min. | `DEFINE RECORD SafetyConfig CONTAINS INTEGER MaxInputTokens AND INTEGER MaxInputBytes AND INTEGER RateLimit AND INTEGER SessionTimeout AND STRING Greeting AND INTEGER ConfidenceMin.` | — |
| `ConnectionStats` | Per-connection analytics: message count, node-hit map, no-match count, connect time, last-message time. | `DEFINE RECORD ConnectionStats CONTAINS INTEGER MessagesReceived AND OBJECT NodeHits AND INTEGER NoMatchCount AND DATA ConnectedAt AND DATA LastMessageAt.` | — |
| `Server` | The chatbot server — holds key, handlers, responses, guardrails, classifiers, safety, bans, analytics. | `DEFINE SERVICE Server CONTAINS RECORD key AND FUNCTION chatHandler AND FUNCTION msgHandler AND ARRAY responses AND ARRAY guardrails AND FUNCTION classifier AND FUNCTION fallbackClassifier AND RECORD safety AND OBJECT bannedKeys AND FUNCTION onAnalytics.` | [VOCAB-GAP: Go's builder pattern with pointer-receiver `*Server` returning `*Server` for chaining — TRL has no verb for mutable-self chain return. Encode as property `builder_chain: true` on each With*/On* FUNCTION node.] |
| `LLMConfig` | LLM classifier configuration: provider, model, API key env var name. | `DEFINE RECORD LLMConfig CONTAINS STRING Provider AND STRING Model AND STRING APIKeyEnv.` | — |

### Vars

| Name | English | TRL | Gap |
|---|---|---|---|
| `DefaultGuardrails` | The 15 compiled-in guardrail ResponseNodes — shipped with every server, checked before business responses. | `DEFINE RESOURCE DefaultGuardrails AS ARRAY OF RECORD ResponseNode CONTAINS 15 RECORD. SERVICE Server SHALL VALIDATE EACH RECORD Message SUBJECT_TO RESOURCE DefaultGuardrails BEFORE ARRAY responses.` | [VOCAB-GAP: "BEFORE" as ordering — used sugar here but TRL has no formal "before" preposition; use `THEN` ordering or node-level `order` property.] |

### Constructor

| Name | English | TRL | Gap |
|---|---|---|---|
| `New(addr)` | Create a Server at `addr` with defaults: auto keypair, 200-token / 2000-byte / 30-per-minute / 30-minute caps, built-in guardrails, default no-match text. | `FUNCTION New SHALL DEFINE SERVICE Server AT ENDPOINT addr THEN BIND RECORD key BY FUNCTION GenerateKeypair THEN BIND RECORD safety AS DEFAULT THEN BIND ARRAY guardrails AS RESOURCE DefaultGuardrails THEN RETURNS_TO SOURCE.` | — |

### Builder methods (all return `*Server`)

Each of the 19 builders is a `FUNCTION ` on `SERVICE Server` that mutates one field and returns SELF. Pattern:

**TRL pattern:**
`FUNCTION ${With*} SHALL REPLACE DATA ${field} ON SELF THEN RETURNS_TO SOURCE SELF.`

Per-builder:

| Name | English | TRL | Gap |
|---|---|---|---|
| `WithSafety(cfg)` | Replace the full safety config. | `FUNCTION WithSafety SHALL REPLACE RECORD safety ON SELF BY RECORD cfg THEN RETURNS_TO SOURCE SELF.` | — |
| `WithGreeting(text)` | Set the first message sent on connect. | `FUNCTION WithGreeting SHALL REPLACE STRING Greeting ON RECORD safety BY STRING text THEN RETURNS_TO SOURCE SELF.` | — |
| `WithGuardrails(path)` | Load extra guardrail nodes from a TRUG file; log on read/parse failure, never propagate. | `FUNCTION WithGuardrails SHALL READ FILE path THEN MAP DATA json AS ARRAY nodes THEN AUGMENT ARRAY guardrails ON SELF BY ARRAY nodes. FUNCTION WithGuardrails SHALL HANDLE EXCEPTION BY WRITE STRING warning TO EXIT log THEN RETURNS_TO SOURCE SELF.` | — |
| `OnAnalytics(fn)` | Install an analytics callback called on every message. | `FUNCTION OnAnalytics SHALL REPLACE FUNCTION onAnalytics ON SELF BY FUNCTION fn THEN RETURNS_TO SOURCE SELF.` | — |
| `WithResponses(nodes)` | Replace the response-node list. | `FUNCTION WithResponses SHALL REPLACE ARRAY responses ON SELF BY ARRAY nodes THEN RETURNS_TO SOURCE SELF.` | — |
| `WithResponsesFromTRUG(path)` | Load response nodes from a .trug.json: each node with `response` (or `description`) becomes a ResponseNode with `keywords`/`name` as keywords. | `FUNCTION WithResponsesFromTRUG SHALL READ FILE path THEN MAP DATA json AS ARRAY nodes THEN FILTER ARRAY nodes BY STRING response EXISTS THEN REPLACE ARRAY responses ON SELF BY RESULT. FUNCTION WithResponsesFromTRUG SHALL HANDLE EXCEPTION BY WRITE STRING warning TO EXIT log THEN RETURNS_TO SOURCE SELF.` | — |
| `WithClassifier(fn)` | Replace the classifier (default is keyword matching). | `FUNCTION WithClassifier SHALL REPLACE FUNCTION classifier ON SELF BY FUNCTION fn THEN RETURNS_TO SOURCE SELF.` | — |
| `WithFallbackClassifier(fn)` | Install an LLM fallback classifier, called only when keyword classifier returns empty AND question count ≤ 20. | `FUNCTION WithFallbackClassifier SHALL REPLACE FUNCTION fallbackClassifier ON SELF BY FUNCTION fn THEN RETURNS_TO SOURCE SELF. SERVICE Server SHALL INVOKE FUNCTION fallbackClassifier IF ARRAY ids EQUALS NONE AND INTEGER questionCount NOT EXCEEDS 20.` | [VOCAB-GAP: "INVOKE" is not in TRL. Use "MAP … BY FUNCTION fallbackClassifier" at call site. Rewrite: `SERVICE Server MAY MAP STRING userText BY FUNCTION fallbackClassifier IF ARRAY ids EQUALS NONE AND INTEGER questionCount NOT EXCEEDS 20.`] |
| `WithNoMatch(text)` | Set the text returned when the classifier finds nothing. | `FUNCTION WithNoMatch SHALL REPLACE STRING noMatchText ON SELF BY STRING text THEN RETURNS_TO SOURCE SELF.` | — |
| `WithContactFooter(footer)` | Append contact info to every response after a blank line. | `FUNCTION WithContactFooter SHALL REPLACE STRING contactFooter ON SELF BY STRING footer THEN RETURNS_TO SOURCE SELF.` | — |
| `OnChat(fn)` DEPRECATED | Legacy: install a free-text handler. | `FUNCTION OnChat SHALL REPLACE FUNCTION chatHandler ON SELF BY FUNCTION fn THEN RETURNS_TO SOURCE SELF. AGENT claude SHALL DEPRECATE FUNCTION OnChat.` | [VOCAB-GAP: same deprecation gap.] |
| `OnMessage(fn)` | Install a full-message handler; takes priority over all CHAT routing. | `FUNCTION OnMessage SHALL REPLACE FUNCTION msgHandler ON SELF BY FUNCTION fn THEN RETURNS_TO SOURCE SELF. SERVICE Server SHALL ROUTE EACH RECORD Message TO FUNCTION msgHandler IF FUNCTION msgHandler EXISTS.` | — |
| `WithTRUG(path)` | Load a .trug.json as read-only chatbot context. | `FUNCTION WithTRUG SHALL READ FILE path AS READONLY THEN REPLACE DATA trugData ON SELF BY DATA THEN RETURNS_TO SOURCE SELF.` | — |
| `WithLLM(provider, model, apiKeyEnv)` | Store LLM configuration (does not wire a classifier). | `FUNCTION WithLLM SHALL DEFINE RECORD LLMConfig CONTAINS STRING provider AND STRING model AND STRING apiKeyEnv THEN REPLACE RECORD llmConfig ON SELF BY RECORD LLMConfig THEN RETURNS_TO SOURCE SELF.` | — |
| `WithUpstream(addr, key)` | Store upstream gateway address + key (fields not actioned in server.go). | `FUNCTION WithUpstream SHALL REPLACE STRING upstreamAddr ON SELF BY STRING addr AND STRING upstreamKey ON SELF BY STRING key THEN RETURNS_TO SOURCE SELF.` | [VOCAB-GAP: "not actioned" = stub. Encode node property `status: "STUB"`.] |
| `Key()` | Return the full server keypair (tests). | `FUNCTION Key SHALL RETURNS_TO SOURCE RECORD key.` | — |
| `PublicKey()` | Return the public key as a hex string. | `FUNCTION PublicKey SHALL MAP STRING public FROM RECORD key AS STRING hex BY FUNCTION KeyToHex THEN RETURNS_TO SOURCE.` | — |
| `GetTRUGContext()` | Return a text summary of loaded TRUG context data. | `FUNCTION GetTRUGContext SHALL MAP DATA trugData AS STRING summary THEN RETURNS_TO SOURCE.` | — |
| `GetResponses()` | Return the loaded response-node list. | `FUNCTION GetResponses SHALL RETURNS_TO SOURCE ARRAY responses.` | — |

### Lifecycle methods

| Name | English | TRL | Gap |
|---|---|---|---|
| `ListenAndServe()` | Start listening; handle SIGINT/SIGTERM via a signal goroutine; spawn one goroutine per accepted connection; block until shutdown. | `FUNCTION ListenAndServe SHALL DEFINE RESOURCE listener BY FUNCTION Listen AT ENDPOINT addr BINDS RECORD key. FUNCTION ListenAndServe SHALL DEFINE PROCESS signal_handler PARALLEL 'that SHALL RECEIVE STREAM sigCh THEN REVOKE RESOURCE listener. FUNCTION ListenAndServe SHALL ROUTE EACH RESOURCE conn FROM RESOURCE listener TO PROCESS serveConn PARALLEL.` | [VOCAB-GAP: `go` keyword / goroutine — encoded via adverb `PARALLEL` on a PROCESS node. `signal.Notify` + OS-signal plumbing — no TRL word; encode as property `signals: ["SIGINT", "SIGTERM"]`.] |
| `ServeListener(ctx, listener)` | Serve on an existing listener; close it when ctx is cancelled; same accept loop as ListenAndServe. | `FUNCTION ServeListener SHALL DEFINE PROCESS ctx_closer PARALLEL 'that SHALL REVOKE RESOURCE listener WHEN STREAM ctx EXPIRES. FUNCTION ServeListener SHALL ROUTE EACH RESOURCE conn FROM RESOURCE listener TO PROCESS serveConn PARALLEL.` | [VOCAB-GAP: context.Context cancellation — `STREAM ctx EXPIRES` is the closest semantic; encode as property `cancellation_signal: "context.Context"`.] |

### Unexported routing / worker methods

| Name | English | TRL | Gap |
|---|---|---|---|
| `defaultClassifier(text, nodes)` | Case-insensitive keyword match; each keyword hit adds 1 to score; return all scoring nodes sorted descending. | `FUNCTION defaultClassifier SHALL MAP STRING userText AS STRING lower THEN MAP EACH RECORD node AS INTEGER score BY FUNCTION count_keyword_matches THEN FILTER ARRAY nodes BY INTEGER score EXCEEDS 0 THEN SORT RESULT BY INTEGER score THEN RETURNS_TO SOURCE ARRAY ids.` | — |
| `buildTRUGContext()` | Walk `trugData.nodes`; emit "- NAME: DESC\n" for each node with a name. | `FUNCTION buildTRUGContext SHALL FILTER ARRAY nodes BY STRING name EXISTS THEN MAP EACH RECORD node AS STRING line THEN AGGREGATE RESULT AS STRING summary THEN RETURNS_TO SOURCE.` | — |
| `serveConn(ctx, conn)` | Per-connection loop: check ban → greet → receive → validate → classify → respond → wind-down/honeypot → close. | See full pipeline decomposition below. | — |
| `handleMessage(msg)` | Thin test wrapper over `handleMessageFull(msg, 0)`. | `FUNCTION handleMessage SHALL MAP RECORD msg BY FUNCTION handleMessageFull 'with INTEGER 0 THEN RETURNS_TO SOURCE RECORD Message.` | — |
| `handleMessageWithStats(msg)` | Thin wrapper over `handleMessageFull(msg, 0)` returning extra flags. | `FUNCTION handleMessageWithStats SHALL MAP RECORD msg BY FUNCTION handleMessageFull 'with INTEGER 0 THEN RETURNS_TO SOURCE RECORD Message AND ARRAY ids AND BOOLEAN hitGuardrail.` | — |
| `handleMessageFull(msg, questionCount)` | Full routing: msgHandler override → CHAT guardrail check → business-response classify → fallback LLM → cap-at-3 → formatting. | See full pipeline decomposition below. | — |
| `mustMarshalJSON(v)` | JSON-marshal swallowing any error. | `FUNCTION mustMarshalJSON SHALL MAP DATA v AS STRING json THEN SKIP EXCEPTION THEN RETURNS_TO SOURCE.` | — |

### Pipeline — `serveConn` (per-connection worker)

**English:** For each accepted Noise connection: (1) check whether its remote public key is banned (permanent or <72h temp); (2) initialise stats, rate-window, counters; (3) send greeting if configured; (4) loop: respect ctx + session timeout; receive; enforce byte-cap and rate-limit; enforce token-cap on CHAT; call `handleMessageFull`; record analytics; on CHAT increment question count; after 20+ CHATs inject per-question sleep `(N-20)*5s`, summary at N=20, farewell + 3-day temp ban at N=40; on guardrail hits escalate honeypot (delay 3/8/15s at tiers 2/3/4, replace response with canned strings at tier 2-4, farewell + ban at tier 5 ≥12); call analytics callback; send response; return on any send/recv error.

**TRL:**
```
PIPELINE serveConn CONTAINS STAGE ban_check AND STAGE greet AND STAGE receive AND STAGE validate
    AND STAGE classify AND STAGE wind_down AND STAGE honeypot AND STAGE send.

STAGE ban_check SHALL READ OBJECT bannedKeys BY STRING keyHex.
STAGE ban_check SHALL REJECT RESOURCE conn IF DATA banTime EXISTS
    AND (DATA banTime EQUALS NONE OR DATA banTime NOT EXPIRE WITHIN 72).
STAGE ban_check SHALL REVOKE DATA banTime IF DATA banTime EXPIRE WITHIN 72.

STAGE greet SHALL SEND RECORD greeting TO RESOURCE conn IF STRING Greeting EXISTS.

STAGE receive SHALL READ DATA FROM RESOURCE conn UNTIL EXCEPTION.
STAGE receive SHALL TIMEOUT WITHIN SessionTimeout IF DATA LastMessageAt EXISTS.

STAGE validate SHALL REJECT DATA IF INTEGER length EXCEEDS MaxInputBytes.
STAGE validate SHALL REJECT DATA IF INTEGER rate EXCEEDS RateLimit WITHIN 60.
STAGE validate SHALL REJECT DATA IF INTEGER tokens EXCEEDS MaxInputTokens.

STAGE classify SHALL MAP RECORD msg BY FUNCTION handleMessageFull THEN AGGREGATE INTEGER questionCount.

STAGE wind_down SHALL TIMEOUT WITHIN DATA delay IF INTEGER questionCount EXCEEDS 20
    WHERE DATA delay EQUALS (INTEGER questionCount MINUS 20) TIMES 5.
STAGE wind_down SHALL REPLACE RECORD response BY RECORD summary IF INTEGER questionCount EQUALS 20.
STAGE wind_down SHALL SEND RECORD farewell THEN WRITE OBJECT bannedKeys AND EXIT
    IF INTEGER questionCount EXCEEDS 39.

STAGE honeypot SHALL AGGREGATE INTEGER guardrailHits IF BOOLEAN hitGuardrail.
STAGE honeypot SHALL TIMEOUT WITHIN 3 IF INTEGER guardrailHits BETWEEN 3 AND 4.
STAGE honeypot SHALL TIMEOUT WITHIN 8 IF INTEGER guardrailHits BETWEEN 5 AND 7.
STAGE honeypot SHALL TIMEOUT WITHIN 15 IF INTEGER guardrailHits EXCEEDS 7.
STAGE honeypot SHALL REPLACE RECORD response BY STRING canned IF INTEGER guardrailHits EXCEEDS 2.
STAGE honeypot SHALL SEND RECORD farewell THEN WRITE OBJECT bannedKeys AND EXIT
    IF INTEGER guardrailHits EXCEEDS 11.

STAGE send SHALL INVOKE FUNCTION onAnalytics IF FUNCTION onAnalytics EXISTS.
STAGE send SHALL SEND RECORD response TO RESOURCE conn.
```

**Gaps:** `[VOCAB-GAP]`s in this pipeline:
1. `BETWEEN`, `MINUS`, `TIMES` — TRL has `EXCEEDS` but no generic arithmetic or range operators. Encode these as node properties (`range: [3,4]`, `delay_formula: "(N-20)*5"`).
2. `TIMEOUT WITHIN N` — TRL `TIMEOUT` is a control verb meaning "fail after N". Here we use it as "sleep for N". Exact semantic mismatch — flag for TRUGS spec issue on a `DELAY` or `PAUSE` verb.
3. `AND EXIT` inside a stage — no TRL verb for "return from goroutine"; use `THEN SHALL_NOT CONTINUE` or encode as `terminal: true` property.
4. `BOOLEAN` — not in TRL's adjective list; TRL uses VALID/INVALID or explicit STRING values. Encode booleans as `RECORD ${name} EQUALS VALID`.

### Pipeline — `handleMessageFull(msg, questionCount)`

**English:** (1) If msgHandler installed, delegate and return. (2) If Type == "CHAT": parse text; run classifier against guardrails; if any match, set hitGuardrail, use first match's response verbatim. Else run classifier against business responses; if empty AND fallbackClassifier AND questionCount ≤ 20, retry with fallback; cap at 3; if empty → noMatchText; else concatenate matched nodes' text with "\n\n". Else if chatHandler → invoke. Else echo text. Format: prepend "You asked about: {text}\n\n" if questionCount > 0; append footer; append "\n\n({questionCount})" if questionCount > 0. Emit CHAT response. (3) Non-CHAT types: echo with same Type/Payload, new UUID, ReplyTo = msg.ID.

**TRL:**
```
FUNCTION handleMessageFull SHALL ROUTE RECORD msg TO FUNCTION msgHandler IF FUNCTION msgHandler EXISTS.

FUNCTION handleMessageFull SHALL MATCH STRING type AS STRING CHAT THEN:
    MAP DATA payload AS STRING userText.
    MAP STRING userText BY FUNCTION classify AGAINST ARRAY guardrails AS ARRAY guardIds.
    IF ARRAY guardIds EXISTS THEN:
        ASSERT BOOLEAN hitGuardrail EQUALS VALID.
        REPLACE STRING responseText BY STRING response OF RECORD guardrail WHERE RECORD guardrail REFERENCES STRING guardIds FIRST.
    ELSE IF ARRAY responses EXISTS THEN:
        MAP STRING userText BY FUNCTION classify AGAINST ARRAY responses AS ARRAY ids.
        IF ARRAY ids EQUALS NONE AND FUNCTION fallbackClassifier EXISTS AND INTEGER questionCount NOT EXCEEDS 20 THEN:
            MAP STRING userText BY FUNCTION fallbackClassifier AGAINST ARRAY responses AS ARRAY ids.
        TAKE 3 FROM ARRAY ids.
        IF ARRAY ids EQUALS NONE THEN REPLACE STRING responseText BY STRING noMatchText.
        ELSE AGGREGATE STRING response FROM EACH RECORD node WHERE RECORD node REFERENCES ARRAY ids AS STRING responseText.
    ELSE IF FUNCTION chatHandler EXISTS THEN MAP STRING userText BY FUNCTION chatHandler AS STRING responseText.
    ELSE REPLACE STRING responseText BY STRING userText.

    IF INTEGER questionCount EXCEEDS 0 THEN AUGMENT STRING responseText BY STRING prefix.
    IF STRING contactFooter EXISTS THEN AUGMENT STRING responseText BY STRING contactFooter.
    IF INTEGER questionCount EXCEEDS 0 THEN AUGMENT STRING responseText BY INTEGER questionCount.

    DEFINE RECORD Message CONTAINS STRING CHAT AND STRING responseText AND STRING id AND STRING msg.id THEN RETURNS_TO SOURCE.

FUNCTION handleMessageFull SHALL DEFINE RECORD Message CONTAINS STRING type AND DATA payload
    AND STRING id AND STRING msg.id THEN RETURNS_TO SOURCE FOR ANY STRING type NOT CHAT.
```

**Gaps:** `IF/ELSE/THEN` are TRL conjunctions and usable as written. `TAKE 3 FROM ARRAY` uses `TAKE` verb (TRL Transform). `AGGREGATE … AS …` uses `AGGREGATE` verb. Inline `OF … WHERE` — `WHERE` is sugar; OF is sugar. `FIRST` is not in TRL — encode as `TAKE 1 FROM ARRAY`.

### Concurrency primitives

| Primitive | English | TRL | Gap |
|---|---|---|---|
| Accept-loop goroutine | One goroutine per accepted connection. | `SERVICE Server SHALL DEFINE PROCESS serveConn PARALLEL FOR EACH RESOURCE conn.` | [VOCAB-GAP: "per-instance" goroutine — PARALLEL adverb is coarse; no vocab for "one goroutine per event".] |
| Signal goroutine | Listens on OS signals, cancels root context, closes listener. | `SERVICE Server SHALL DEFINE PROCESS signal_handler PARALLEL 'that SHALL RECEIVE STREAM sigCh.` | — |
| `sigCh` channel | 1-capacity channel for SIGINT/SIGTERM. | `DEFINE STREAM sigCh BOUNDED WITHIN 1 RECEIVES os.Signal.` | — |
| `context.Context` | Cancellation signal tree. | `DEFINE STREAM ctx FEEDS PROCESS serveConn AND PROCESS signal_handler.` | [VOCAB-GAP: ctx semantics (hierarchical cancellation) not directly expressible.] |
| `bannedMu sync.RWMutex` | Read-write lock on `bannedKeys` map. | n/a | [VOCAB-GAP: lock primitive — encode as node property `concurrency: "rwmutex"`.] |
| `rateMu sync.Mutex` (per conn) | Lock on per-conn rate-window slice. | n/a | [VOCAB-GAP: same.] |

### Persistence

| Op | English | TRL | Gap |
|---|---|---|---|
| `os.ReadFile` — guardrails / responses / context TRUGs | Load a .trug.json file once on configuration. | `FUNCTION WithGuardrails SHALL READ FILE path ONCE AS READONLY. FUNCTION WithResponsesFromTRUG SHALL READ FILE path ONCE AS READONLY. FUNCTION WithTRUG SHALL READ FILE path ONCE AS READONLY.` | — |
| `bannedKeys map[string]time.Time` | In-memory bans that expire after 72h (no persistence across restarts). | `DEFINE RESOURCE bannedKeys AS OBJECT STRING TO DATA. EACH ENTRY OF RESOURCE bannedKeys SHALL EXPIRE WITHIN 72 HOURS.` | [VOCAB-GAP: TRL has no time-unit vocabulary — encode as `expire_seconds: 259200`.] |
| `messageTimestamps []time.Time` (per conn) | Sliding 1-minute window of message send times. | `DEFINE RESOURCE messageTimestamps AS ARRAY OF DATA BOUNDED WITHIN 60. EACH DATA SHALL EXPIRE WITHIN 60.` | [VOCAB-GAP: same — seconds.] |
| `trugData`, `responses`, `guardrails` | Loaded once via builders, immutable thereafter. | `EACH DATA loaded_via_builder SHALL BE IMMUTABLE AFTER ENTRY configuration.` | — |

---

## Package `client`

### Module header

**TRL:**
`MODULE client CONTAINS FUNCTION Connect AND FUNCTION Chat AND FUNCTION Send AND FUNCTION Close. MODULE client DEPENDS_ON MODULE noise AND MODULE protocol. FUNCTION Connect SHALL AUTHENTICATE SUBJECT_TO RECORD server_public_key.`

### Symbols

| Name | English | TRL | Gap |
|---|---|---|---|
| `Client` (type) | An encrypted client — wraps a single NoiseConn. | `DEFINE RECORD Client CONTAINS RECORD conn.` | — |
| `Connect(addr, hex)` | Decode the server's hex pubkey, generate an ephemeral client static keypair, TCP-dial, handshake. | `FUNCTION Connect SHALL MAP STRING hex AS STRING serverPub BY FUNCTION HexToKey THEN DEFINE RECORD clientKey BY FUNCTION GenerateKeypair THEN REQUEST RECORD NoiseConn FROM ENDPOINT addr SUBJECT_TO STRING serverPub BY FUNCTION Dial THEN RETURNS_TO SOURCE RECORD Client.` | — |
| `(*Client).Chat(text)` | Send a CHAT message, await a response, extract `text` payload field. | `FUNCTION Chat SHALL DEFINE RECORD Message CONTAINS STRING CHAT AND OBJECT text THEN SEND RESULT TO ENDPOINT server THEN RECEIVE RESULT AS RECORD Message THEN MAP DATA payload AS STRING response THEN RETURNS_TO SOURCE.` | — |
| `(*Client).Send(msg)` | Marshal + send + receive + unmarshal a full Message. | `FUNCTION Send SHALL MAP RECORD msg AS STRING json THEN SEND STRING json TO RECORD conn THEN RECEIVE STRING json FROM RECORD conn THEN MAP STRING json AS RECORD Message THEN RETURNS_TO SOURCE.` | — |
| `(*Client).Close()` | Close the underlying Noise connection. | `FUNCTION Close SHALL REVOKE RECORD conn.` | — |
| `mustMarshal` (unexp) | Marshal `any` to JSON, swallow errors. | `FUNCTION mustMarshal SHALL MAP DATA v AS STRING json THEN SKIP EXCEPTION THEN RETURNS_TO SOURCE.` | — |

### Message ID convention

**English:** Client message IDs are `"msg-"` + `time.Now().UnixNano()` in decimal.
**TRL:** `EACH RECORD Message FROM MODULE client SHALL CONTAIN STRING id AS UNIQUE STRING FROM DATA clock.`

### Error conventions

Same wrapping pattern as `noise` — all errors `fmt.Errorf("...: %w", err)`, no named types.
`FUNCTION ANY IN MODULE client SHALL THROW EXCEPTION 'that CONTAINS STRING context AND RECORD inner.`

---

## Binary `helper/noise-helper`

### Process header

**TRL:**
`DEFINE PROCESS helper. PROCESS helper READS RECORD Message FROM ENTRY stdin THEN SEND RESULT TO ENDPOINT server. PROCESS helper READS RECORD Message FROM ENDPOINT server THEN WRITE RESULT TO EXIT stdout. EACH RECORD Message SHALL AUTHENTICATE BY RECORD noise_ik.`

### CLI surface

| Name | English | TRL | Gap |
|---|---|---|---|
| Binary `noise-helper` | stdin/stdout bridge for non-Go clients over Noise_IK. | `DEFINE INTERFACE noise-helper CONTAINS ENTRY stdin AND EXIT stdout AND EXIT stderr.` | — |
| `--server HOST:PORT` | Server address, default `localhost:9090`. | `DEFINE RECORD flag_server AS STRING DEFAULT "localhost:9090".` | — |
| `--key HEX` (required) | Server public key in hex; exits with error if missing. | `DEFINE RECORD flag_key AS REQUIRED STRING. PROCESS helper SHALL REJECT ENTRY IF STRING flag_key EQUALS NONE.` | — |
| stdout `"CONNECTED"` | Printed after successful handshake. | `PROCESS helper SHALL WRITE STRING CONNECTED TO EXIT stdout AFTER AUTHENTICATE.` | [VOCAB-GAP: "AFTER" — use `THEN` for ordering in a pipeline; here it's causal. Acceptable.] |
| stderr `"ERROR: ..."` | Printed on setup/send/recv failures. | `PROCESS helper SHALL WRITE STRING error TO EXIT stderr IF EXCEPTION EXISTS.` | — |
| Exit 0 on recv EOF | Reader goroutine treats EOF as clean exit. | `PROCESS helper SHALL EXIT WITH INTEGER 0 IF STREAM server EQUALS NONE.` | [VOCAB-GAP: "exit code" — no TRL vocabulary; encode as property `exit_codes: {clean: 0, error: 1}`.] |
| Exit 1 on setup/send failure | Setup failures and send failures exit non-zero. | `PROCESS helper SHALL EXIT WITH INTEGER 1 IF EXCEPTION FROM STAGE setup OR STAGE send.` | — |

### Goroutines

| Name | English | TRL | Gap |
|---|---|---|---|
| reader goroutine | Receives from server, writes to stdout. | `DEFINE PROCESS reader PARALLEL 'that SHALL RECEIVE DATA FROM ENDPOINT server THEN WRITE RESULT TO EXIT stdout UNTIL EXCEPTION.` | — |
| main scan loop | Reads stdin JSON lines, sends to server. | `PROCESS helper SHALL READ STRING json FROM ENTRY stdin THEN VALIDATE STRING json AS JSON THEN SEND STRING json TO ENDPOINT server FOR EACH STRING json.` | [VOCAB-GAP: "JSON" as a format validator — use property `format: "json"` on RECORD.] |

### Buffer sizing

**English:** scanner buffer 16 MiB (`scanner.Buffer(16*1024*1024, 16*1024*1024)`).
**TRL:** `PROCESS helper SHALL BOUND DATA buffer WITHIN 16777216.`

---

## Package `examples`

### `echo`

**English:** Start server on `:9090`; OnChat returns `"You said: "` + input verbatim.
**TRL:**
```
STAGE echo SHALL DEFINE SERVICE Server AT ENDPOINT ":9090" THEN BIND FUNCTION chatHandler
    AS FUNCTION map_to_prefix.
FUNCTION map_to_prefix SHALL MAP STRING text AS STRING concat WHERE STRING concat EQUALS "You said: " PLUS STRING text.
```
**Gap:** `[VOCAB-GAP: string concatenation — TRL has no CONCAT or PLUS verb. Encode as node property `output_format: "You said: {input}"`.]`

### `faq`

**English:** Load `faq.json` as Q→A map; OnChat runs case-insensitive substring match; fallback lists available keys.
**TRL:**
```
STAGE faq SHALL READ FILE "faq.json" ONCE AS READONLY THEN MAP DATA AS OBJECT questions_to_answers.
STAGE faq SHALL DEFINE SERVICE Server AT ENDPOINT ":9090" THEN BIND FUNCTION chatHandler AS FUNCTION keyword_lookup.
FUNCTION keyword_lookup SHALL MAP STRING text AS STRING lower THEN FILTER OBJECT questions_to_answers
    BY STRING question CONTAINS STRING lower THEN TAKE 1 FROM RESULT.
FUNCTION keyword_lookup SHALL RESPOND STRING fallback IF RESULT EQUALS NONE
    WHERE STRING fallback CONTAINS STRING "I don't have an answer for that. Try asking about: " AND STRING keys.
```
**Gap:** same string-concat gap as echo.

### `llm`

**English:** Configure LLM (`"anthropic"`, `"claude-haiku-4-5"`, `"ANTHROPIC_API_KEY"`); OnChat returns a stub message. Classifier not wired.
**TRL:**
```
STAGE llm SHALL DEFINE SERVICE Server AT ENDPOINT ":9090" THEN BIND RECORD LLMConfig
    CONTAINS STRING "anthropic" AND STRING "claude-haiku-4-5" AND STRING "ANTHROPIC_API_KEY".
STAGE llm SHALL BIND FUNCTION chatHandler AS FUNCTION stub_placeholder.
FUNCTION stub_placeholder SHALL RESPOND STRING "LLM integration coming soon. You asked: " PLUS STRING text.
```
**Gap:** `status: "STUB"` — classifier integration not implemented.

### `graph`

**English:** Load `knowledge.trug.json` as context; OnChat returns a stub message.
**TRL:**
```
STAGE graph SHALL DEFINE SERVICE Server AT ENDPOINT ":9090"
    THEN READ FILE "knowledge.trug.json" ONCE AS READONLY THEN REPLACE DATA trugData.
STAGE graph SHALL BIND FUNCTION chatHandler AS FUNCTION stub_placeholder.
```
**Gap:** `status: "STUB"` — graph-backed response not implemented.

---

## VOCAB-GAP Consolidated Register

These gaps are flagged here, not resolved locally. Each becomes either:
- an A3 node property on the relevant FUNCTION/SERVICE node (concrete encoding), or
- a TRUGS language issue for vocabulary expansion (if the concept is general).

| # | Gap | Scope | A3 encoding (proposed) | TRUGS issue candidate? |
|---|---|---|---|---|
| 1 | Lock primitive (`sync.Mutex`, `sync.RWMutex`) | `NoiseConn`, `Server.bannedMu`, per-conn `rateMu` | `properties.concurrency: "mutex" \| "rwmutex"` | No — encoding is sufficient; locks are implementation detail. |
| 2 | Goroutine spawn (`go fn()`) | `server.ListenAndServe`, `ServeListener`, `helper.main` | `PROCESS` node with `parallel: true`; edge `SPAWNS` → `PARALLEL` adverb on the edge relation | Maybe — TRL has `PARALLEL` adverb but no `SPAWN` verb. Propose `SPAWN` or formalise `PROCESS … PARALLEL` pattern. |
| 3 | Channel (`chan T`) | `sigCh` | `STREAM` node with `capacity: int`, `element_type: string` | No — `STREAM` covers it. |
| 4 | Context cancellation (`context.Context`) | Server lifecycle | `STREAM ctx` with edge `GOVERNS` into each PARALLEL PROCESS | Maybe — TRL has no "hierarchical cancellation" primitive. Low priority. |
| 5 | Noise_IK handshake pattern (`-> e, es, s, ss / <- e, ee, se`) | `ClientHandshake`, `ServerHandshake` | `properties.noise_pattern: "IK"`, `properties.message_sequence: [...]` | No — cryptographic jargon, not general TRL concern. |
| 6 | Length-prefix framing (uint32 BE) | `NoiseConn.Send/Receive`, `writeFrame/readFrame` | `properties.frame_format: "uint32_be_length_prefix"`, `properties.max_frame_bytes: 16777216 / 65536` | No. |
| 7 | Builder pattern (`*Server → *Server`) | All `With*` / `On*` methods on `Server` | `properties.builder_chain: true`, `returns: "self"` | Maybe — TRL has no formal way to express "fluent API". Low priority. |
| 8 | Deprecation (`ChatHandler`, `OnChat`) | `server` | `properties.deprecated: true`, `properties.deprecated_reason: "..."` | Yes — `DEPRECATE` is a common API-evolution word. Propose addition. |
| 9 | "Invoke" / function call | Pervasive | Use `MAP X BY FUNCTION f` (already covered) | No — `MAP BY` is fine. |
| 10 | "Per-instance" / "per-event" goroutine | `server.serveConn` | `properties.parallelism: "per-connection"` | Maybe — no TRL way to say "one PARALLEL PROCESS per input event". Propose formalisation. |
| 11 | `TIMEOUT WITHIN N` used as "sleep N" vs "fail after N" | Honeypot tiers, wind-down delay | Use `PAUSE` or `DELAY` — not in TRL. For now: `properties.sleep_seconds: int` | **Yes — clear TRL gap.** Propose `DELAY` or `PAUSE` verb. |
| 12 | Arithmetic (`MINUS`, `TIMES`, ranges like `BETWEEN 3 AND 4`) | Wind-down delay formula, honeypot tiers | `properties.formula: "(N-20)*5"`, `properties.range: [low, high]` | Maybe — TRL is declarative by design; arithmetic may be out of scope. |
| 13 | `BOOLEAN` adjective | Pervasive (flags, hitGuardrail, etc.) | Use `EQUALS VALID` / `EQUALS INVALID` (already TRL-valid) | No — handled. |
| 14 | String concatenation (`+` in Go) | Examples, honeypot canned strings | `properties.template: "{prefix} {field}"` | Maybe — formatters / templating are a general need. Low priority. |
| 15 | Exit code / process exit | `helper` binary | `properties.exit_codes: {clean: 0, error: 1}` | No — shell-level concern, not TRL core. |
| 16 | Time units (seconds, minutes, hours) | Bans (72h), session timeout (30m), rate window (60s), wind-down delay | `properties.expire_seconds: int`, `properties.window_seconds: int` | Maybe — TRL `WITHIN` is dimensionless; adding units would bloat vocabulary. Keep as property. |
| 17 | "Before" / ordering adjective | DefaultGuardrails "checked first" | Use explicit `THEN` in pipelines; or `properties.priority: int` | No — `THEN` handles ordering. |
| 18 | `SELF` pronoun scoping in builder methods | All `With*` methods | TRL `SELF` exists; confirm semantics in TRUGS_PROTOCOL | No — TRL covers it. |
| 19 | Format validators (JSON, hex, etc.) | helper input validation, key decoding | `properties.format: "json" \| "hex"` | No. |
| 20 | `FIRST` / "take one" | Guardrail first-match, nodeIDs[0] | Use `TAKE 1 FROM ARRAY` | No — `TAKE 1` works. |

**High-value TRUGS spec issues surfaced:**
- #TRL-001: `DELAY` / `PAUSE` verb (Gap 11) — concrete need in every tar-pit / back-pressure / rate-limiting system.
- #TRL-002: `DEPRECATE` verb or modal modifier (Gap 8) — concrete need for any evolving API surface.
- #TRL-003: Per-event parallelism pattern (Gap 10) — formalise `PROCESS ... PARALLEL FOR EACH` or add `SPAWN PER` phrasing.

These are proposals, not decisions. Route to TRUGS language owner in Phase A5 VALIDATION or via TRUGS protocol issue thread.

---

## Symbol → TRL-sentence coverage

Against A1 inventory symbol count:

| Package | A1 symbols | A2 sentences written | Coverage |
|---|---:|---:|---:|
| `noise` | 14 | 14 + 2 header + 3 error-conventions | 100% |
| `protocol` | 1 | 1 + 1 module + 2 payload shapes | 100% |
| `server` | 31 | 8 types + 1 var + 1 ctor + 19 builders + 2 lifecycle + 7 unexported = 38; + 2 pipelines; + 6 concurrency + 4 persistence | 100% (31/31 exported covered; unexported routing also covered) |
| `client` | 5 | 5 + 1 header + 1 ID convention + 1 error convention | 100% |
| `helper` | CLI binary | 7 rows + 2 goroutine rows + 1 buffer row | 100% |
| `examples/*` | 4 binaries | 4 stage blocks | 100% |

**Total exported library symbols translated: 51 / 51.**
**Binaries: 5 / 5** (helper + 4 examples).
**Unexported routing/helper functions translated: 7** (defaultClassifier, buildTRUGContext, serveConn, handleMessage, handleMessageWithStats, handleMessageFull, mustMarshalJSON).

Test functions (35) are not part of the exported surface — their contracts will be expressed as A4 parity fixtures rather than A2 sentences.

---

## Parked questions (for A3 or A5 VALIDATION)

Inherited from A1, now with A2 translation context:

1. **`bannedKeys` permanent-ban branch** — A2 TRL writes `DATA banTime EQUALS NONE OR DATA banTime NOT EXPIRE WITHIN 72`. Since no caller writes zero-time, the `EQUALS NONE` branch is dead. Either remove in A3 (simpler TRUG) or preserve and flag as `status: "DEAD_CODE"` property.
2. **`handleMessage` and `handleMessageWithStats` are identical delegators** — A3 TRUG should collapse to a single FUNCTION node `handleMessageFull` with two thin-wrapper IMPLEMENTS edges, or flag the wrappers as `status: "DEPRECATED_ALIAS"`.
3. **`WithLLM` without `WithClassifier` is a no-op** — A2 TRL captures the storage but not the wiring. A3 should edge `FUNCTION WithLLM DEPENDS_ON FUNCTION WithClassifier` with property `coupling: "manual"`.
4. **`WithUpstream` fields are stored but not read** — Flag node `WithUpstream` with `status: "STUB"`.
5. **Permanent-ban semantics** (see 1) and **`time.Sleep` as TIMEOUT** (Gap 11) are the two items likely to produce spec-level TRUGS issues.
6. **`DefaultGuardrails` duality** — compiled-in `var DefaultGuardrails` in `server.go` AND `guardrails.trug.json` on disk are two sources of truth for the same 15 entries. A3 picks one as canonical; propose the compiled-in list since the JSON mirror is consumed via `WithGuardrails` (additive, not overriding).
7. **`mustMarshalJSON` swallows errors** — A2 TRL uses `SKIP EXCEPTION`, but `SKIP` is a TRL Transform verb meaning "drop records". Semantic overlap is acceptable but tight. Flag as `properties.error_handling: "swallow"`.

---

**End of A2.** Next: A3 — build `noise_chatbot.super.trug.json` from these sentences. Nodes per `### Symbols` rows, hierarchy per package, edges per module-header DEPENDS_ON / CONTAINS / FEEDS relations. Function count must match **51 public + 7 unexported = 58 FUNCTION nodes** (+ pipeline STAGE nodes).
