#!/usr/bin/env python3
"""Build noise_chatbot.super.trug.json from A1 inventory + A2 TRL sentences.

Produces a CORE-valid TRUG: 7 required node fields, 3 edge fields,
parent metric_level >= child metric_level within same dimension.
All edge relations use TRL prepositions (CONTAINS, DEPENDS_ON,
IMPLEMENTS, FEEDS, ROUTES, REFERENCES, GOVERNS, BINDS).
"""

import json
from pathlib import Path

# Metric level plan:
# MEGA_PROJECT  — root
# KILO_MODULE   — each Go package
# HECTO_SERVICE — long-running services (Server)
# DEKA_RECORD   — types
# DEKA_INTERFACE — public CLI/binary surfaces
# DEKA_STAGE    — pipeline stages
# BASE_FUNCTION — every Go function/method
# BASE_RESOURCE — listeners, vars, config files
# BASE_PROCESS  — goroutines
# BASE_STREAM   — channels, contexts

DIM = "code"

nodes = []
edges = []


def N(node_id, ntype, metric, parent_id, contains, props, dim=DIM):
    nodes.append({
        "id": node_id,
        "type": ntype,
        "properties": props,
        "parent_id": parent_id,
        "contains": list(contains),
        "metric_level": metric,
        "dimension": dim,
    })


def E(from_id, to_id, relation, props=None):
    e = {"from_id": from_id, "to_id": to_id, "relation": relation}
    if props:
        e["properties"] = props
    edges.append(e)


# ── Root ────────────────────────────────────────────────────────────────

ROOT = "root_project"

# ── Module IDs ──────────────────────────────────────────────────────────

mod_ids = {
    "noise":    "mod_noise",
    "protocol": "mod_protocol",
    "server":   "mod_server",
    "client":   "mod_client",
    "helper":   "mod_helper",
    "examples": "mod_examples",
}

# ─────────────────────────────────────────────────────────────────────────
# mod_noise children
# ─────────────────────────────────────────────────────────────────────────

noise_records = ["rec_DHKey", "rec_NoiseConn", "rec_Listener"]
noise_resources = ["res_CipherSuite"]
noise_funcs_exported = [
    ("fn_GenerateKeypair",      "GenerateKeypair",      "noise.go",   "top-level"),
    ("fn_KeyToHex",             "KeyToHex",             "noise.go",   "top-level"),
    ("fn_HexToKey",             "HexToKey",             "noise.go",   "top-level"),
    ("fn_NoiseConn_Send",       "(*NoiseConn).Send",    "conn.go",    "method"),
    ("fn_NoiseConn_Receive",    "(*NoiseConn).Receive", "conn.go",    "method"),
    ("fn_NoiseConn_Close",      "(*NoiseConn).Close",   "conn.go",    "method"),
    ("fn_NoiseConn_RemoteIdentity", "(*NoiseConn).RemoteIdentity", "conn.go", "method"),
    ("fn_Dial",                 "Dial",                 "client.go",  "top-level"),
    ("fn_ClientHandshake",      "ClientHandshake",      "client.go",  "top-level"),
    ("fn_Listen",               "Listen",               "server.go",  "top-level"),
    ("fn_Listener_Accept",      "(*Listener).Accept",   "server.go",  "method"),
    ("fn_Listener_Close",       "(*Listener).Close",    "server.go",  "method"),
    ("fn_Listener_Addr",        "(*Listener).Addr",     "server.go",  "method"),
    ("fn_ServerHandshake",      "ServerHandshake",      "server.go",  "top-level"),
]
noise_funcs_unexported = [
    ("fn_writeFrame", "writeFrame", "frame.go", "top-level-unexported"),
    ("fn_readFrame",  "readFrame",  "frame.go", "top-level-unexported"),
]
noise_all_fns = noise_funcs_exported + noise_funcs_unexported

noise_children = noise_records + noise_resources + [nid for nid, _, _, _ in noise_all_fns]

# ─────────────────────────────────────────────────────────────────────────
# mod_protocol children
# ─────────────────────────────────────────────────────────────────────────

protocol_children = ["rec_Message"]

# ─────────────────────────────────────────────────────────────────────────
# mod_server children
# ─────────────────────────────────────────────────────────────────────────

server_records = [
    "rec_ResponseNode",
    "rec_Classifier",
    "rec_ChatHandler",
    "rec_MessageHandler",
    "rec_SafetyConfig",
    "rec_ConnectionStats",
    "rec_LLMConfig",
]

server_service = "svc_Server"
server_resources = ["res_DefaultGuardrails"]

server_funcs_exported = [
    ("fn_New",                        "New",                        "constructor"),
    ("fn_Server_WithSafety",          "(*Server).WithSafety",       "builder"),
    ("fn_Server_WithGreeting",        "(*Server).WithGreeting",     "builder"),
    ("fn_Server_WithGuardrails",     "(*Server).WithGuardrails",   "builder"),
    ("fn_Server_OnAnalytics",         "(*Server).OnAnalytics",      "builder"),
    ("fn_Server_WithResponses",       "(*Server).WithResponses",    "builder"),
    ("fn_Server_WithResponsesFromTRUG", "(*Server).WithResponsesFromTRUG", "builder"),
    ("fn_Server_WithClassifier",      "(*Server).WithClassifier",   "builder"),
    ("fn_Server_WithFallbackClassifier", "(*Server).WithFallbackClassifier", "builder"),
    ("fn_Server_WithNoMatch",         "(*Server).WithNoMatch",      "builder"),
    ("fn_Server_WithContactFooter",   "(*Server).WithContactFooter","builder"),
    ("fn_Server_OnChat",              "(*Server).OnChat",           "builder-DEPRECATED"),
    ("fn_Server_OnMessage",           "(*Server).OnMessage",        "builder"),
    ("fn_Server_WithTRUG",            "(*Server).WithTRUG",         "builder"),
    ("fn_Server_WithLLM",             "(*Server).WithLLM",          "builder"),
    ("fn_Server_WithUpstream",        "(*Server).WithUpstream",     "builder-STUB"),
    ("fn_Server_Key",                 "(*Server).Key",              "getter"),
    ("fn_Server_PublicKey",           "(*Server).PublicKey",        "getter"),
    ("fn_Server_GetTRUGContext",      "(*Server).GetTRUGContext",   "getter"),
    ("fn_Server_GetResponses",        "(*Server).GetResponses",     "getter"),
    ("fn_Server_ListenAndServe",      "(*Server).ListenAndServe",   "lifecycle"),
    ("fn_Server_ServeListener",       "(*Server).ServeListener",    "lifecycle"),
]

server_funcs_unexported = [
    ("fn_defaultClassifier",          "defaultClassifier",          "routing"),
    ("fn_Server_buildTRUGContext",    "(*Server).buildTRUGContext", "helper"),
    ("fn_Server_serveConn",           "(*Server).serveConn",        "worker"),
    ("fn_Server_handleMessage",       "(*Server).handleMessage",    "routing-thin-wrapper"),
    ("fn_Server_handleMessageWithStats", "(*Server).handleMessageWithStats", "routing-thin-wrapper"),
    ("fn_Server_handleMessageFull",   "(*Server).handleMessageFull", "routing-core"),
    ("fn_mustMarshalJSON",            "mustMarshalJSON",            "helper"),
]

server_stages = [
    ("stage_serveConn",          "serveConn pipeline"),
    ("stage_handleMessageFull",  "handleMessageFull routing pipeline"),
]

server_processes = [
    ("proc_signal_handler",  "SIGINT/SIGTERM goroutine"),
    ("proc_ctx_closer",      "ServeListener ctx-close goroutine"),
    ("proc_accept_loop",     "accept-loop goroutine (spawns per-conn workers)"),
    ("proc_serveConn_worker", "per-connection goroutine (one per accept)"),
]

server_streams = [
    ("stream_sigCh", "chan os.Signal (cap 1)"),
    ("stream_ctx",   "context.Context cancellation"),
]

server_all_fns = server_funcs_exported + server_funcs_unexported
server_children = (
    server_records
    + [server_service]
    + server_resources
    + [nid for nid, _, _ in server_all_fns]
    + [nid for nid, _ in server_stages]
    + [nid for nid, _ in server_processes]
    + [nid for nid, _ in server_streams]
)

# ─────────────────────────────────────────────────────────────────────────
# mod_client children
# ─────────────────────────────────────────────────────────────────────────

client_records = ["rec_Client"]
client_funcs_exported = [
    ("fn_Connect",       "Connect",           "top-level"),
    ("fn_Client_Chat",   "(*Client).Chat",    "method"),
    ("fn_Client_Send",   "(*Client).Send",    "method"),
    ("fn_Client_Close",  "(*Client).Close",   "method"),
]
client_funcs_unexported = [
    ("fn_client_mustMarshal", "mustMarshal", "helper"),
]
client_all_fns = client_funcs_exported + client_funcs_unexported
client_children = client_records + [nid for nid, _, _ in client_all_fns]

# ─────────────────────────────────────────────────────────────────────────
# mod_helper children
# ─────────────────────────────────────────────────────────────────────────

helper_iface = "iface_helper_cli"
helper_funcs = [
    ("fn_helper_main",   "main",   "binary-entry-point"),
    ("fn_helper_reader", "reader goroutine", "unexported-closure"),
]
helper_process = [
    ("proc_helper_reader", "server→stdout reader goroutine"),
    ("proc_helper_main",   "stdin→server main loop"),
]
helper_resources = [
    ("res_flag_server", "CLI flag --server (default localhost:9090)"),
    ("res_flag_key",    "CLI flag --key (required, hex)"),
]
helper_children = (
    [helper_iface]
    + [nid for nid, _, _ in helper_funcs]
    + [nid for nid, _ in helper_process]
    + [nid for nid, _ in helper_resources]
)

# ─────────────────────────────────────────────────────────────────────────
# mod_examples children
# ─────────────────────────────────────────────────────────────────────────

examples_ifaces = [
    ("iface_echo",  "examples/echo/main.go",  "OnChat echoes input"),
    ("iface_faq",   "examples/faq/main.go",   "keyword lookup over faq.json"),
    ("iface_llm",   "examples/llm/main.go",   "LLM stub (WithLLM configured, classifier unwired)"),
    ("iface_graph", "examples/graph/main.go", "graph-backed stub (WithTRUG loads knowledge.trug.json)"),
]
examples_children = [nid for nid, _, _ in examples_ifaces]

# ─────────────────────────────────────────────────────────────────────────
# Build nodes
# ─────────────────────────────────────────────────────────────────────────

# Root
N(ROOT, "NAMESPACE", "MEGA_NAMESPACE", None,
  contains=list(mod_ids.values()),
  props={
      "name": "noise_chatbot.super.trug.json",
      "source_repo": "github.com/TRUGS-LLC/noise-chatbot",
      "go_module": "github.com/TRUGS-LLC/noise-chatbot",
      "go_version": "1.24.0",
      "license": "Apache-2.0",
      "description": "Standalone black-box specification of the Go noise-chatbot implementation — super-TRUG for Python rewrite. Encrypted chatbot framework using Noise_IK (Curve25519 + ChaCha20-Poly1305 + BLAKE2b).",
      "phase": "A3",
      "inputs": ["REFERENCE/A1_inventory.md", "REFERENCE/A2_trl_sentences.md"],
      "inventory_counts": {
          "exported_symbols": 55,
          "exported_funcs_methods": 40,
          "exported_types": 13,
          "exported_vars": 2,
          "unexported_routing_funcs": 10,
          "binaries": 5,
          "packages": 6,
      },
      "external_deps": {
          "github.com/flynn/noise": "v1.1.0",
          "github.com/google/uuid": "v1.6.0",
      },
  })

# Modules
for pkg_path, mid in mod_ids.items():
    children_map = {
        "noise":    noise_children,
        "protocol": protocol_children,
        "server":   server_children,
        "client":   client_children,
        "helper":   helper_children,
        "examples": examples_children,
    }
    N(mid, "MODULE", "KILO_MODULE", ROOT,
      contains=children_map[pkg_path],
      props={
          "package": pkg_path,
          "path": f"{pkg_path}/",
          "role": {
              "noise":    "Noise_IK TCP transport (handshake + length-prefixed framed encryption).",
              "protocol": "Wire envelope Message type (JSON).",
              "server":   "Chatbot server — template-mode LLM classification + honeypot + wind-down.",
              "client":   "Go client library.",
              "helper":   "stdin/stdout Noise_IK bridge binary (noise-helper) for non-Go clients.",
              "examples": "Four example binaries: echo, faq, llm, graph.",
          }[pkg_path],
      })

# ── mod_noise contents ──────────────────────────────────────────────────

N("rec_DHKey", "RECORD", "DEKA_RECORD", "mod_noise", [], {
    "name": "DHKey",
    "kind": "type-alias",
    "go_type": "noiselib.DHKey",
    "fields": ["public", "private"],
    "trl": "DEFINE RECORD DHKey CONTAINS STRING public AND STRING private.",
    "notes": "Re-export of flynn/noise static keypair type.",
})

N("rec_NoiseConn", "RECORD", "DEKA_RECORD", "mod_noise", [], {
    "name": "NoiseConn",
    "kind": "struct",
    "fields": ["conn", "encrypt", "decrypt", "remote"],
    "concurrency_safe": True,
    "concurrency_impl": "sync.Mutex mu (writes) + sync.Mutex rmu (reads) — two separate mutexes permit concurrent read+write",
    "trl": "DEFINE RECORD NoiseConn CONTAINS RESOURCE conn AND DATA encrypt AND DATA decrypt AND STRING remote.",
    "vocab_gap": "sync.Mutex fields mu/rmu — no TRL word for lock primitive; encoded as properties only.",
})

N("rec_Listener", "RECORD", "DEKA_RECORD", "mod_noise", [], {
    "name": "Listener",
    "kind": "struct",
    "fields": ["inner", "serverKey"],
    "trl": "DEFINE RECORD Listener CONTAINS RESOURCE inner AND RECORD serverKey.",
})

N("res_CipherSuite", "RESOURCE", "BASE_RESOURCE", "mod_noise", [], {
    "name": "CipherSuite",
    "kind": "package-var",
    "immutable": True,
    "contents": "NewCipherSuite(DH25519, CipherChaChaPoly, HashBLAKE2b)",
    "trl": "DEFINE RESOURCE CipherSuite AS IMMUTABLE DATA.",
    "notes": "Fixed cipher suite — no negotiation.",
})

for fid, name, src, kind in noise_all_fns:
    N(fid, "FUNCTION", "BASE_FUNCTION", "mod_noise", [], {
        "name": name,
        "package": "noise",
        "source_file": src,
        "exported": not fid.startswith("fn_write") and not fid.startswith("fn_read"),
        "kind": kind,
        "error_pattern": "fmt.Errorf wrapping via %w",
    })

# ── mod_protocol contents ───────────────────────────────────────────────

N("rec_Message", "RECORD", "DEKA_RECORD", "mod_protocol", [], {
    "name": "Message",
    "kind": "struct",
    "fields": ["Type", "Payload", "ID", "ReplyTo"],
    "field_types": {
        "Type":    "string",
        "Payload": "json.RawMessage",
        "ID":      "string",
        "ReplyTo": "string (omitempty)",
    },
    "known_type_values": ["CHAT", "ERROR"],
    "known_payload_shapes": {
        "CHAT":  "{text: string}",
        "ERROR": "{error: string}",
    },
    "trl": "DEFINE RECORD Message CONTAINS STRING type AND DATA payload AND STRING id AND OPTIONAL STRING reply_to.",
})

# ── mod_server contents ─────────────────────────────────────────────────

server_record_info = {
    "rec_ResponseNode":    ("ResponseNode", "struct", ["ID", "Keywords", "Response"],
                            "DEFINE RECORD ResponseNode CONTAINS STRING id AND ARRAY keywords AND STRING response."),
    "rec_Classifier":      ("Classifier", "func-type",
                            "func(userText string, nodes []ResponseNode) []string",
                            "DEFINE FUNCTION Classifier SHALL MAP STRING userText AND ARRAY nodes AS ARRAY ids."),
    "rec_ChatHandler":     ("ChatHandler", "func-type-DEPRECATED",
                            "func(text string) string",
                            "DEFINE FUNCTION ChatHandler SHALL MAP STRING text AS STRING response."),
    "rec_MessageHandler":  ("MessageHandler", "func-type",
                            "func(msg protocol.Message) protocol.Message",
                            "DEFINE FUNCTION MessageHandler SHALL MAP RECORD Message AS RECORD Message."),
    "rec_SafetyConfig":    ("SafetyConfig", "struct",
                            ["MaxInputTokens", "MaxInputBytes", "RateLimit",
                             "SessionTimeout", "Greeting", "ConfidenceMin"],
                            "DEFINE RECORD SafetyConfig CONTAINS INTEGER MaxInputTokens AND INTEGER MaxInputBytes AND INTEGER RateLimit AND INTEGER SessionTimeout AND STRING Greeting AND INTEGER ConfidenceMin."),
    "rec_ConnectionStats": ("ConnectionStats", "struct",
                            ["MessagesReceived", "NodeHits", "NoMatchCount",
                             "ConnectedAt", "LastMessageAt"],
                            "DEFINE RECORD ConnectionStats CONTAINS INTEGER MessagesReceived AND OBJECT NodeHits AND INTEGER NoMatchCount AND DATA ConnectedAt AND DATA LastMessageAt."),
    "rec_LLMConfig":       ("LLMConfig", "struct",
                            ["Provider", "Model", "APIKeyEnv"],
                            "DEFINE RECORD LLMConfig CONTAINS STRING Provider AND STRING Model AND STRING APIKeyEnv."),
}

for rid, info in server_record_info.items():
    name = info[0]
    kind = info[1]
    if kind.startswith("func-type"):
        _, _, signature, trl = info
        props = {"name": name, "kind": kind, "signature": signature, "trl": trl}
    else:
        _, _, fields, trl = info
        props = {"name": name, "kind": kind, "fields": fields, "trl": trl}
    if "DEPRECATED" in kind:
        props["deprecated"] = True
    N(rid, "RECORD", "DEKA_RECORD", "mod_server", [], props)

N("svc_Server", "SERVICE", "HECTO_SERVICE", "mod_server", [], {
    "name": "Server",
    "kind": "struct",
    "role": "long-running chatbot server with template-mode classification",
    "addr_default_example": ":9090",
    "auto_keygen_on_new": True,
    "default_safety": {
        "MaxInputTokens": 200,
        "MaxInputBytes":  2000,
        "RateLimit":      30,
        "SessionTimeout_minutes": 30,
        "ConfidenceMin":  1,
    },
    "default_no_match_text": "I don't have information about that. Please contact us directly.",
    "loads_default_guardrails_on_new": True,
    "trl": "DEFINE SERVICE Server CONTAINS RECORD key AND FUNCTION chatHandler AND FUNCTION msgHandler AND ARRAY responses AND ARRAY guardrails AND FUNCTION classifier AND FUNCTION fallbackClassifier AND RECORD safety AND OBJECT bannedKeys AND FUNCTION onAnalytics.",
    "vocab_gaps": [
        "Builder pattern (*Server→*Server chain) — encode as builder_chain: true on each With*/On* FUNCTION.",
        "sync.RWMutex bannedMu / sync.Mutex rateMu — encoded as properties only."
    ],
})

N("res_DefaultGuardrails", "RESOURCE", "BASE_RESOURCE", "mod_server", [], {
    "name": "DefaultGuardrails",
    "kind": "package-var",
    "immutable_source": True,
    "count": 15,
    "entries": [
        "guard-identity", "guard-creator", "guard-admin", "guard-password",
        "guard-apikey", "guard-prompt", "guard-inject", "guard-personal",
        "guard-others", "guard-harmful", "guard-offtopic", "guard-distress",
        "guard-capabilities", "guard-language", "guard-feedback",
    ],
    "trl": "DEFINE RESOURCE DefaultGuardrails AS ARRAY OF RECORD ResponseNode CONTAINS 15 RECORD.",
    "duplicate_source_note": "15 entries are also in guardrails.trug.json (disk copy, additively loaded via WithGuardrails).",
})

for fid, name, kind in server_all_fns:
    N(fid, "FUNCTION", "BASE_FUNCTION", "mod_server", [], {
        "name": name,
        "package": "server",
        "source_file": "server.go",
        "exported": not name.startswith("(") and name[0].isupper() or name in (
            # methods that are on Server type are exported if the method name starts uppercase
        ),
        "kind": kind,
        "builder_chain": kind == "builder" or kind.startswith("builder-"),
        "deprecated": "DEPRECATED" in kind,
        "stub": "STUB" in kind,
    })

# Override exported flag — cleaner: any fn not starting with fn_defaultClassifier or containing _handle/_serveConn/_buildTRUG/_mustMarshal/_handleMessageWithStats etc. treat as derived from naming
_unexported_ids = {
    "fn_defaultClassifier", "fn_Server_buildTRUGContext",
    "fn_Server_serveConn", "fn_Server_handleMessage",
    "fn_Server_handleMessageWithStats", "fn_Server_handleMessageFull",
    "fn_mustMarshalJSON", "fn_writeFrame", "fn_readFrame",
    "fn_client_mustMarshal",
}
for n in nodes:
    if n["type"] == "FUNCTION":
        n["properties"]["exported"] = n["id"] not in _unexported_ids

# Stages
N("stage_serveConn", "STAGE", "DEKA_STAGE", "mod_server", [], {
    "name": "serveConn",
    "pipeline_stages": [
        "ban_check",   # check bannedKeys
        "greet",       # send greeting if configured
        "receive",     # read from NoiseConn with timeout
        "validate",    # enforce byte-cap, rate-limit, token-cap
        "classify",    # call handleMessageFull
        "wind_down",   # N>=20 sleep, N==20 summary, N>=40 farewell+ban
        "honeypot",    # guardrail tier escalation 3/8/15s, tier 5 farewell+ban
        "send",        # send response, call onAnalytics
    ],
    "state": {
        "stats":                "ConnectionStats per connection",
        "messageTimestamps":    "sliding 1-minute rate window (per conn)",
        "guardrailHits":        "counter for honeypot escalation",
        "questionCount":        "counter for wind-down triggers",
    },
    "trl_block": "See REFERENCE/A2_trl_sentences.md §Pipeline — serveConn",
})

N("stage_handleMessageFull", "STAGE", "DEKA_STAGE", "mod_server", [], {
    "name": "handleMessageFull",
    "pipeline_stages": [
        "msgHandler_override",   # if msgHandler set, delegate
        "guardrail_check",       # classify against guardrails
        "responses_classify",    # classify against business responses
        "fallback_llm",          # only if questionCount <= 20 and primary empty
        "match_cap",             # cap at 3 matched IDs
        "format",                # build final response text
    ],
    "formatting_rules": {
        "prefix_when_q_gt_0": "You asked about: {text}\\n\\n{response}",
        "contact_footer":     "{response}\\n\\n{contactFooter}",
        "count_suffix":       "{response}\\n\\n({questionCount})",
    },
    "trl_block": "See REFERENCE/A2_trl_sentences.md §Pipeline — handleMessageFull",
})

# Processes
N("proc_signal_handler", "PROCESS", "BASE_PROCESS", "mod_server", [], {
    "name": "signal_handler",
    "parallel": True,
    "spawned_from": "fn_Server_ListenAndServe",
    "waits_on": "stream_sigCh",
    "signals": ["SIGINT", "SIGTERM"],
    "action_on_signal": "cancel root context and close listener",
    "vocab_gap": "goroutine / OS-signal plumbing not in TRL — encoded as properties.",
})

N("proc_ctx_closer", "PROCESS", "BASE_PROCESS", "mod_server", [], {
    "name": "ctx_closer",
    "parallel": True,
    "spawned_from": "fn_Server_ServeListener",
    "waits_on": "stream_ctx",
    "action_on_done": "close listener",
})

N("proc_accept_loop", "PROCESS", "BASE_PROCESS", "mod_server", [], {
    "name": "accept_loop",
    "parallel": False,
    "role": "main accept loop in ListenAndServe / ServeListener; spawns per-connection workers",
    "per_event_parallelism": "spawns proc_serveConn_worker per accepted connection",
    "vocab_gap": "'one goroutine per accepted connection' — PARALLEL adverb is coarse; no TRL for per-event spawn.",
})

N("proc_serveConn_worker", "PROCESS", "BASE_PROCESS", "mod_server", [], {
    "name": "serveConn_worker",
    "parallel": True,
    "spawned_per": "connection",
    "body": "stage_serveConn",
    "lifecycle": "until recv error, ctx cancel, session timeout, or honeypot/wind-down ban",
})

# Streams
N("stream_sigCh", "STREAM", "BASE_STREAM", "mod_server", [], {
    "name": "sigCh",
    "capacity": 1,
    "element_type": "os.Signal",
    "created_by": "fn_Server_ListenAndServe",
    "signals_registered": ["SIGINT", "SIGTERM"],
})

N("stream_ctx", "STREAM", "BASE_STREAM", "mod_server", [], {
    "name": "ctx",
    "element_type": "context.Context",
    "role": "root cancellation tree; feeds signal_handler and serveConn_worker",
    "vocab_gap": "context.Context hierarchical cancellation — no TRL primitive.",
})

# ── mod_client contents ─────────────────────────────────────────────────

N("rec_Client", "RECORD", "DEKA_RECORD", "mod_client", [], {
    "name": "Client",
    "kind": "struct",
    "fields": ["conn"],
    "trl": "DEFINE RECORD Client CONTAINS RECORD conn.",
})

for fid, name, kind in client_all_fns:
    N(fid, "FUNCTION", "BASE_FUNCTION", "mod_client", [], {
        "name": name,
        "package": "client",
        "source_file": "client.go",
        "exported": fid != "fn_client_mustMarshal",
        "kind": kind,
        "error_pattern": "fmt.Errorf wrapping via %w",
    })

# ── mod_helper contents ─────────────────────────────────────────────────

N(helper_iface, "INTERFACE", "DEKA_INTERFACE", "mod_helper", [], {
    "name": "noise-helper",
    "kind": "cli-binary",
    "build_cmd": "go build -o noise-helper ./helper",
    "flags": {
        "--server": {"type": "string", "default": "localhost:9090", "required": False},
        "--key":    {"type": "string", "required": True, "format": "hex-32-bytes"},
    },
    "stdout_contract": {
        "CONNECTED":   "printed after successful handshake",
        "message_out": "raw JSON received from server + \\n",
    },
    "stderr_contract": {
        "ERROR: ...": "printed on setup/send/recv failures",
    },
    "exit_codes": {"clean_recv_eof": 0, "setup_or_send_error": 1, "missing_key": 1},
    "stdin_buffer_bytes": 16 * 1024 * 1024,
    "trl": "DEFINE INTERFACE noise-helper CONTAINS ENTRY stdin AND EXIT stdout AND EXIT stderr.",
})

N("fn_helper_main", "FUNCTION", "BASE_FUNCTION", "mod_helper", [], {
    "name": "main",
    "package": "helper",
    "source_file": "helper/main.go",
    "exported": False,
    "kind": "binary-entry-point",
    "role": "parse flags → handshake → spawn reader goroutine → stdin scan loop",
})

N("fn_helper_reader", "FUNCTION", "BASE_FUNCTION", "mod_helper", [], {
    "name": "reader-goroutine-closure",
    "package": "helper",
    "source_file": "helper/main.go",
    "exported": False,
    "kind": "goroutine-closure",
    "role": "receive from server, write to stdout, os.Exit(0) on recv error (EOF = clean)",
})

N("proc_helper_reader", "PROCESS", "BASE_PROCESS", "mod_helper", [], {
    "name": "helper_reader",
    "parallel": True,
    "body": "fn_helper_reader",
    "lifecycle": "until server disconnects",
})

N("proc_helper_main", "PROCESS", "BASE_PROCESS", "mod_helper", [], {
    "name": "helper_main",
    "parallel": False,
    "role": "main stdin→server loop (bufio.Scanner with 16 MiB buffer)",
})

N("res_flag_server", "RESOURCE", "BASE_RESOURCE", "mod_helper", [], {
    "name": "--server",
    "flag_type": "string",
    "default": "localhost:9090",
    "required": False,
})

N("res_flag_key", "RESOURCE", "BASE_RESOURCE", "mod_helper", [], {
    "name": "--key",
    "flag_type": "string",
    "required": True,
    "format": "hex-encoded 32-byte Curve25519 public key",
})

# ── mod_examples contents ───────────────────────────────────────────────

example_details = {
    "iface_echo": {
        "role": "simplest bot — echoes input",
        "listen_addr": ":9090",
        "handler": "OnChat(text => \"You said: \" + text)",
        "external_input": None,
    },
    "iface_faq": {
        "role": "FAQ bot — loads faq.json, case-insensitive keyword match",
        "listen_addr": ":9090",
        "handler": "substring Q→A lookup; fallback lists available keys",
        "external_input": "faq.json (cwd)",
    },
    "iface_llm": {
        "role": "LLM bot — stubbed",
        "listen_addr": ":9090",
        "llm_config": "anthropic / claude-haiku-4-5 / ANTHROPIC_API_KEY",
        "status": "STUB",
        "handler": "\"LLM integration coming soon. You asked: \" + text",
    },
    "iface_graph": {
        "role": "Graph-backed bot — stubbed",
        "listen_addr": ":9090",
        "handler": "\"Graph-backed response coming soon. You asked: \" + text",
        "external_input": "knowledge.trug.json (cwd)",
        "status": "STUB",
    },
}

for iid, src_file, desc in examples_ifaces:
    detail = example_details[iid]
    N(iid, "INTERFACE", "DEKA_INTERFACE", "mod_examples", [], {
        "name": iid.replace("iface_", ""),
        "kind": "example-binary",
        "source_file": src_file,
        "description": desc,
        **detail,
    })

# ─────────────────────────────────────────────────────────────────────────
# Edges — DEPENDS_ON between modules (per import graph)
# ─────────────────────────────────────────────────────────────────────────

# Module import DAG:
#   protocol — standalone
#   noise    — depends on flynn/noise (external)
#   server   — DEPENDS_ON noise, protocol, google/uuid
#   client   — DEPENDS_ON noise, protocol
#   helper   — DEPENDS_ON noise
#   examples — DEPENDS_ON server

E("mod_server",   "mod_noise",    "DEPENDS_ON", {"import": "github.com/TRUGS-LLC/noise-chatbot/noise"})
E("mod_server",   "mod_protocol", "DEPENDS_ON", {"import": "github.com/TRUGS-LLC/noise-chatbot/protocol"})
E("mod_client",   "mod_noise",    "DEPENDS_ON", {"import": "github.com/TRUGS-LLC/noise-chatbot/noise"})
E("mod_client",   "mod_protocol", "DEPENDS_ON", {"import": "github.com/TRUGS-LLC/noise-chatbot/protocol"})
E("mod_helper",   "mod_noise",    "DEPENDS_ON", {"import": "github.com/TRUGS-LLC/noise-chatbot/noise"})
E("mod_examples", "mod_server",   "DEPENDS_ON", {"import": "github.com/TRUGS-LLC/noise-chatbot/server"})

# ─────────────────────────────────────────────────────────────────────────
# Edges — IMPLEMENTS
# ─────────────────────────────────────────────────────────────────────────

# Server IMPLEMENTS chatbot_server interface (abstract — see AGENT.md)
# Server BINDS to rec_SafetyConfig etc. via its fields — skip edge, captured in properties.

# handleMessageFull IMPLEMENTS the routing invariant: every CHAT Message routes here
E("fn_Server_handleMessageFull", "rec_Message", "REFERENCES",
  {"role": "entry-point for every Message when no msgHandler override"})

# handleMessage / handleMessageWithStats are thin wrappers
E("fn_Server_handleMessage",          "fn_Server_handleMessageFull", "IMPLEMENTS",
  {"role": "thin wrapper with questionCount=0"})
E("fn_Server_handleMessageWithStats", "fn_Server_handleMessageFull", "IMPLEMENTS",
  {"role": "thin wrapper returning extra flags"})

# serveConn IMPLEMENTS stage_serveConn
E("fn_Server_serveConn",          "stage_serveConn",         "IMPLEMENTS")
E("fn_Server_handleMessageFull",  "stage_handleMessageFull", "IMPLEMENTS")

# ─────────────────────────────────────────────────────────────────────────
# Edges — FEEDS / ROUTES (data flow)
# ─────────────────────────────────────────────────────────────────────────

# The signal channel feeds the signal handler
E("stream_sigCh", "proc_signal_handler", "FEEDS",
  {"payload": "os.Signal (SIGINT or SIGTERM)"})

# ctx feeds both signal_handler and serveConn_worker (cancellation signal)
E("stream_ctx", "proc_signal_handler",  "FEEDS", {"role": "cancellation"})
E("stream_ctx", "proc_serveConn_worker", "FEEDS", {"role": "cancellation"})
E("stream_ctx", "proc_ctx_closer",       "FEEDS", {"role": "cancellation"})

# accept_loop spawns serveConn workers per connection
E("proc_accept_loop", "proc_serveConn_worker", "FEEDS",
  {"role": "spawns one PARALLEL PROCESS per accepted connection",
   "vocab_gap": "TRL has no 'SPAWN PER' pattern — encoded as property."})

# ListenAndServe and ServeListener launch the signal_handler / ctx_closer
E("fn_Server_ListenAndServe", "proc_signal_handler", "FEEDS", {"role": "spawns"})
E("fn_Server_ListenAndServe", "proc_accept_loop",    "FEEDS", {"role": "is"})
E("fn_Server_ServeListener",  "proc_ctx_closer",     "FEEDS", {"role": "spawns"})
E("fn_Server_ServeListener",  "proc_accept_loop",    "FEEDS", {"role": "is"})

# serveConn_worker calls into stage_serveConn
E("proc_serveConn_worker", "stage_serveConn", "ROUTES",
  {"role": "per-message dispatch"})

# stage_serveConn routes messages to handleMessageFull
E("stage_serveConn", "stage_handleMessageFull", "ROUTES",
  {"role": "after validate stage, classify stage delegates to handleMessageFull"})

# ─────────────────────────────────────────────────────────────────────────
# Edges — GOVERNS (safety, guardrails over message flow)
# ─────────────────────────────────────────────────────────────────────────

E("res_DefaultGuardrails", "rec_Message", "GOVERNS",
  {"role": "every CHAT Message is classified against guardrails FIRST"})

E("rec_SafetyConfig", "stage_serveConn", "GOVERNS",
  {"role": "MaxInputBytes, RateLimit, MaxInputTokens, SessionTimeout, Greeting, ConfidenceMin"})

E("svc_Server", "rec_Message", "GOVERNS",
  {"role": "Server governs every Message — ROUTE invariant"})

# ─────────────────────────────────────────────────────────────────────────
# Edges — REFERENCES (functions to types)
# ─────────────────────────────────────────────────────────────────────────

# noise package internal references
E("fn_Dial",            "fn_ClientHandshake", "REFERENCES",
  {"role": "Dial calls ClientHandshake after TCP dial"})
E("fn_Listener_Accept", "fn_ServerHandshake", "REFERENCES",
  {"role": "Accept calls ServerHandshake after TCP accept"})
E("fn_NoiseConn_Send",    "res_CipherSuite", "REFERENCES", {"role": "uses encrypt CipherState"})
E("fn_NoiseConn_Receive", "res_CipherSuite", "REFERENCES", {"role": "uses decrypt CipherState"})
E("fn_Dial",            "fn_writeFrame", "REFERENCES", {"role": "handshake framing"})
E("fn_Dial",            "fn_readFrame",  "REFERENCES")
E("fn_Listener_Accept", "fn_writeFrame", "REFERENCES")
E("fn_Listener_Accept", "fn_readFrame",  "REFERENCES")
E("fn_GenerateKeypair", "rec_DHKey",     "REFERENCES")

# server builder methods reference what they install
E("fn_Server_WithResponses",          "rec_ResponseNode",      "REFERENCES")
E("fn_Server_WithResponsesFromTRUG",  "rec_ResponseNode",      "REFERENCES")
E("fn_Server_WithClassifier",         "rec_Classifier",        "REFERENCES")
E("fn_Server_WithFallbackClassifier", "rec_Classifier",        "REFERENCES")
E("fn_Server_OnChat",                 "rec_ChatHandler",       "REFERENCES",
  {"deprecated_target": True})
E("fn_Server_OnMessage",              "rec_MessageHandler",    "REFERENCES")
E("fn_Server_WithSafety",             "rec_SafetyConfig",      "REFERENCES")
E("fn_Server_WithLLM",                "rec_LLMConfig",         "REFERENCES")
E("fn_Server_WithGuardrails",         "rec_ResponseNode",      "REFERENCES",
  {"role": "loads JSON TRUG and appends to guardrails"})
E("fn_New",                           "svc_Server",            "REFERENCES", {"role": "constructs"})
E("fn_New",                           "res_DefaultGuardrails", "REFERENCES", {"role": "loads on construction"})

# handleMessageFull references records it touches
E("fn_Server_handleMessageFull", "rec_ResponseNode",    "REFERENCES")
E("fn_Server_handleMessageFull", "rec_ConnectionStats", "REFERENCES")
E("fn_Server_handleMessageFull", "rec_Classifier",      "REFERENCES")

# serveConn references safety + stats
E("fn_Server_serveConn", "rec_SafetyConfig",     "REFERENCES")
E("fn_Server_serveConn", "rec_ConnectionStats",  "REFERENCES")
E("fn_Server_serveConn", "stream_ctx",           "REFERENCES")

# client funcs reference their dependencies
E("fn_Connect",          "fn_HexToKey",          "REFERENCES")
E("fn_Connect",          "fn_GenerateKeypair",   "REFERENCES")
E("fn_Connect",          "fn_Dial",              "REFERENCES")
E("fn_Client_Chat",      "rec_Message",          "REFERENCES")
E("fn_Client_Send",      "rec_Message",          "REFERENCES")
E("fn_Client_Send",      "fn_NoiseConn_Send",    "REFERENCES")
E("fn_Client_Send",      "fn_NoiseConn_Receive", "REFERENCES")

# helper references
E("fn_helper_main", "res_flag_server", "REFERENCES")
E("fn_helper_main", "res_flag_key",    "REFERENCES")
E("fn_helper_main", "fn_HexToKey",    "REFERENCES")
E("fn_helper_main", "fn_Dial",        "REFERENCES")
E("fn_helper_main", "fn_GenerateKeypair", "REFERENCES")
E("fn_helper_main", "proc_helper_reader", "REFERENCES", {"role": "spawns reader goroutine"})
E("fn_helper_reader", "fn_NoiseConn_Receive", "REFERENCES")

# examples reference server builder surface
for iid in ["iface_echo", "iface_faq", "iface_llm", "iface_graph"]:
    E(iid, "fn_New",          "REFERENCES")
    E(iid, "fn_Server_OnChat","REFERENCES", {"deprecated_target": True})
    E(iid, "fn_Server_ListenAndServe", "REFERENCES")
E("iface_llm",   "fn_Server_WithLLM",  "REFERENCES")
E("iface_graph", "fn_Server_WithTRUG", "REFERENCES")

# ─────────────────────────────────────────────────────────────────────────
# Graph
# ─────────────────────────────────────────────────────────────────────────

graph = {
    "name":    "noise_chatbot.super.trug",
    "version": "1.0.0",
    "type":    "SUPER_TRUG",
    "dimensions": {
        DIM: {
            "description": "The production code surface of the Go noise-chatbot implementation, spanning 6 packages, plus concurrency and pipeline structure."
        }
    },
    "capabilities": {
        "extensions": [],
        "vocabularies": ["TRL-190"],
        "profiles": ["super_trug"],
    },
    "nodes": nodes,
    "edges": edges,
    "metadata": {
        "source_repo":     "github.com/TRUGS-LLC/noise-chatbot",
        "source_inventory": "REFERENCE/A1_inventory.md",
        "source_trl":      "REFERENCE/A2_trl_sentences.md",
        "phase":           "A3",
        "issue":           "1555",
        "author":          "Claude Opus 4.7 (1M context) + Xepayac",
        "node_counts_by_type": {},  # filled below
    },
}

# Fill node-counts
counts = {}
for n in nodes:
    counts[n["type"]] = counts.get(n["type"], 0) + 1
graph["metadata"]["node_counts_by_type"] = counts

# Summary stats
graph["metadata"]["total_nodes"] = len(nodes)
graph["metadata"]["total_edges"] = len(edges)

# Validate basic consistency before writing
node_ids = {n["id"] for n in nodes}
# Check parent/child bidirectional
errors = []
for n in nodes:
    pid = n.get("parent_id")
    if pid is not None and pid not in node_ids:
        errors.append(f"Node {n['id']} parent_id {pid} not in node set")
    if pid is not None:
        parent = next((x for x in nodes if x["id"] == pid), None)
        if parent and n["id"] not in parent.get("contains", []):
            errors.append(f"Node {n['id']} claims parent {pid} but not in parent.contains")
    for cid in n.get("contains", []):
        if cid not in node_ids:
            errors.append(f"Node {n['id']} contains[] has unknown child {cid}")
        child = next((x for x in nodes if x["id"] == cid), None)
        if child and child.get("parent_id") != n["id"]:
            errors.append(f"Node {n['id']} contains {cid} but child parent_id = {child.get('parent_id')}")

# Check edges
for e in edges:
    if e["from_id"] not in node_ids:
        errors.append(f"Edge from_id {e['from_id']} dangling")
    if e["to_id"] not in node_ids:
        errors.append(f"Edge to_id {e['to_id']} dangling")

if errors:
    print(f"CONSISTENCY ERRORS: {len(errors)}")
    for err in errors[:20]:
        print("  " + err)
    import sys; sys.exit(1)

print(f"✓ {len(nodes)} nodes, {len(edges)} edges")
print(f"Node types: {counts}")

# Write
out_path = Path("REFERENCE/noise_chatbot.super.trug.json")
out_path.parent.mkdir(exist_ok=True)
with open(out_path, "w") as f:
    json.dump(graph, f, indent=2)
print(f"Wrote {out_path}")
