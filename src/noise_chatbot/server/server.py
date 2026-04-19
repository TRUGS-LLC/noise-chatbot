"""The chatbot Server — long-running service with builder API.

<trl>
MODULE server CONTAINS SERVICE Server.
SERVICE Server IMPLEMENTS INTERFACE chatbot_server.
SERVICE Server CONTAINS RECORD key AND FUNCTION chat_handler AND FUNCTION msg_handler
    AND ARRAY responses AND ARRAY guardrails AND FUNCTION classifier
    AND FUNCTION fallback_classifier AND RECORD safety AND OBJECT banned_keys
    AND FUNCTION on_analytics.
AGENT SHALL_NOT WRITE ANY RECORD response 'that 'is NOT FROM RECORD ResponseNode.
</trl>
"""

from __future__ import annotations

import json
import logging
import signal as _signal
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from noise_chatbot.noise.keys import DHKey, generate_keypair, key_to_hex
from noise_chatbot.noise.server import Listener, listen
from noise_chatbot.protocol.message import Message
from noise_chatbot.stores import (
    BannedKeyStore,
    GuardrailStore,
    InMemoryBannedKeyStore,
    InMemoryGuardrailStore,
    InMemoryKnowledgeBaseStore,
    InMemoryResponseStore,
    JsonFileKnowledgeBaseStore,
    JsonFileResponseStore,
    KnowledgeBaseStore,
    ResponseStore,
)

if TYPE_CHECKING:
    from noise_chatbot.noise.conn import NoiseConn
    from noise_chatbot.server.classifier import Classifier

_log = logging.getLogger("noise_chatbot.server")


# <trl>
# DEFINE FUNCTION ChatHandler SHALL MAP STRING text AS STRING response.
# AGENT claude SHALL DEPRECATE FUNCTION ChatHandler.
# </trl>
ChatHandler = Callable[[str], str]
"""DEPRECATED: legacy free-text chat handler."""

# <trl>DEFINE FUNCTION MessageHandler SHALL MAP RECORD Message AS RECORD Message.</trl>
MessageHandler = Callable[[Message], Message]


# AGENT responsenode SHALL DEFINE RECORD.
@dataclass(slots=True)
class ResponseNode:
    """A pre-authored response — ID, keywords, verbatim text.

    <trl>
    DEFINE RECORD ResponseNode CONTAINS STRING id AND ARRAY keywords AND STRING response.
    </trl>
    """

    id: str
    keywords: list[str]
    response: str


# AGENT safetyconfig SHALL DEFINE RECORD.
@dataclass(slots=True)
class SafetyConfig:
    """Per-server safety knobs.

    <trl>
    DEFINE RECORD SafetyConfig CONTAINS INTEGER max_input_tokens
        AND INTEGER max_input_bytes AND INTEGER rate_limit
        AND INTEGER session_timeout AND STRING greeting AND INTEGER confidence_min.
    </trl>
    """

    max_input_tokens: int = 200
    max_input_bytes: int = 2000
    rate_limit: int = 30
    session_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    greeting: str = ""
    confidence_min: int = 1


# AGENT connectionstats SHALL DEFINE RECORD.
@dataclass(slots=True)
class ConnectionStats:
    """Per-connection analytics counters."""

    messages_received: int = 0
    node_hits: dict[str, int] = field(default_factory=dict)
    no_match_count: int = 0
    connected_at: datetime | None = None
    last_message_at: datetime | None = None


# AGENT llmconfig SHALL DEFINE RECORD.
@dataclass(slots=True)
class LLMConfig:
    """LLM classifier configuration — stored, not auto-wired."""

    provider: str
    model: str
    api_key_env: str


AnalyticsCallback = Callable[[ConnectionStats, str, list[str]], None]

# Wire-level text. Exact strings are under parity assertion — do not edit
# without updating fixtures 09, 10, 21.
_ERR_TOO_LARGE = "message too large"
_ERR_RATE_LIMIT = "rate limit exceeded, please slow down"
_TEXT_TOKEN_CAP = "Please keep your message shorter \u2014 I work best with concise questions."
_TEXT_DEFAULT_NO_MATCH = "I don't have information about that. Please contact us directly."

# Wind-down + honeypot constants (Go parity).
_WIND_DOWN_START = 20
_WIND_DOWN_END = 40
_WIND_DOWN_PER_Q_DELAY_SECS = 5
_BAN_DURATION = timedelta(hours=72)
_HONEYPOT_TIER2_HITS = 3
_HONEYPOT_TIER3_HITS = 5
_HONEYPOT_TIER4_HITS = 8
_HONEYPOT_TIER5_HITS = 12
_HONEYPOT_TIER2_DELAY_SECS = 3
_HONEYPOT_TIER3_DELAY_SECS = 8
_HONEYPOT_TIER4_DELAY_SECS = 15
_MATCH_CAP = 3
_TOKEN_CHARS_PER_TOKEN = 4


# AGENT chatbot_server SHALL RECEIVE DATA THEN SEND DATA.
class Server:
    """Encrypted chatbot server — template mode + honeypot + wind-down."""

    __slots__ = (
        "_addr",
        "_banned_key_store",
        "_chat_handler",
        "_classifier",
        "_contact_footer",
        "_fallback_classifier",
        "_guardrail_store",
        "_guardrails",
        "_key",
        "_knowledge_base_store",
        "_listener",
        "_llm_config",
        "_msg_handler",
        "_no_match_text",
        "_on_analytics",
        "_response_store",
        "_responses",
        "_safety",
        "_stop",
        "_trug_data",
        "_upstream_addr",
        "_upstream_key",
    )

    def __init__(self, addr: str) -> None:
        """Create a Server with safe defaults.

        <trl>
        FUNCTION New SHALL DEFINE SERVICE Server AT ENDPOINT addr
            THEN BIND RECORD key BY FUNCTION generate_keypair
            THEN BIND RECORD safety AS DEFAULT
            THEN BIND ARRAY guardrails AS RESOURCE DEFAULT_GUARDRAILS.
        </trl>
        """
        from noise_chatbot.server.guardrails import DEFAULT_GUARDRAILS

        self._addr = addr
        self._key: DHKey = generate_keypair()
        self._chat_handler: ChatHandler | None = None
        self._msg_handler: MessageHandler | None = None
        self._trug_data: dict[str, Any] | None = None
        self._llm_config: LLMConfig | None = None
        self._upstream_addr: str = ""
        self._upstream_key: str = ""
        self._responses: list[ResponseNode] = []
        self._guardrails: list[ResponseNode] = [
            ResponseNode(id=n.id, keywords=list(n.keywords), response=n.response)
            for n in DEFAULT_GUARDRAILS
        ]
        self._classifier: Classifier | None = None
        self._fallback_classifier: Classifier | None = None
        self._no_match_text: str = _TEXT_DEFAULT_NO_MATCH
        self._safety = SafetyConfig()
        # Store protocols — default to in-memory, override via with_*_store builders.
        # The store is the source of truth for API; internal lists above are the
        # hot path updated by builders.
        self._guardrail_store: GuardrailStore = InMemoryGuardrailStore(list(self._guardrails))
        self._response_store: ResponseStore = InMemoryResponseStore()
        self._banned_key_store: BannedKeyStore = InMemoryBannedKeyStore(ttl=_BAN_DURATION)
        self._knowledge_base_store: KnowledgeBaseStore = InMemoryKnowledgeBaseStore()
        self._contact_footer: str = ""
        self._on_analytics: AnalyticsCallback | None = None
        self._listener: Listener | None = None
        self._stop = threading.Event()

    # ── Builder methods ──────────────────────────────────────────────

    # FUNCTION with_safety SHALL DEFINE RECORD.
    def with_safety(self, cfg: SafetyConfig) -> Server:
        self._safety = cfg
        return self

    # FUNCTION with_greeting SHALL DEFINE DATA.
    def with_greeting(self, text: str) -> Server:
        self._safety.greeting = text
        return self

    # FUNCTION with_guardrails SHALL READ DATA.
    def with_guardrails(self, path: str | Path) -> Server:
        """Append custom guardrail nodes from a TRUG JSON file to the
        compiled-in defaults. If a non-``InMemoryGuardrailStore`` has been
        injected via ``with_guardrail_store()``, it's replaced with a new
        in-memory store combining the current guardrails + the loaded ones.
        """
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            _log.warning("could not load guardrails %s: %s", path, exc)
            return self
        try:
            trug = json.loads(data)
        except json.JSONDecodeError:
            return self
        new_nodes: list[ResponseNode] = []
        for node in trug.get("nodes", []):
            props = node.get("properties", {}) or {}
            response = props.get("response", "")
            if not response:
                continue
            keywords = [k for k in props.get("keywords", []) if isinstance(k, str)]
            new_nodes.append(
                ResponseNode(id=node.get("id", ""), keywords=keywords, response=response)
            )
        if isinstance(self._guardrail_store, InMemoryGuardrailStore):
            self._guardrail_store.extend(new_nodes)
        else:
            # Non-extendable store — rebuild as InMemoryGuardrailStore with current + new.
            combined = [*self._guardrail_store.guardrails(), *new_nodes]
            self._guardrail_store = InMemoryGuardrailStore(combined)
        self._guardrails = list(self._guardrail_store.guardrails())
        _log.info("Loaded %d guardrail nodes from %s", len(new_nodes), path)
        return self

    # FUNCTION on_analytics SHALL DEFINE PROCESS.
    def on_analytics(self, fn: AnalyticsCallback) -> Server:
        self._on_analytics = fn
        return self

    # FUNCTION with_responses SHALL DEFINE DATA.
    def with_responses(self, nodes: list[ResponseNode]) -> Server:
        self._responses = list(nodes)
        return self

    # FUNCTION with_responses_from_trug SHALL READ DATA.
    def with_responses_from_trug(self, path: str | Path) -> Server:
        """Load response nodes from a TRUG JSON file (thin wrapper over
        ``JsonFileResponseStore`` for backwards compatibility)."""
        store = JsonFileResponseStore(path)
        self.with_response_store(store)
        _log.info("Loaded %d response nodes from %s", len(self._responses), path)
        return self

    # FUNCTION with_classifier SHALL DEFINE PROCESS.
    def with_classifier(self, classifier: Classifier) -> Server:
        self._classifier = classifier
        return self

    # FUNCTION with_fallback_classifier SHALL DEFINE PROCESS.
    def with_fallback_classifier(self, classifier: Classifier) -> Server:
        self._fallback_classifier = classifier
        return self

    # FUNCTION with_no_match SHALL DEFINE DATA.
    def with_no_match(self, text: str) -> Server:
        self._no_match_text = text
        return self

    # FUNCTION with_contact_footer SHALL DEFINE DATA.
    def with_contact_footer(self, footer: str) -> Server:
        self._contact_footer = footer
        return self

    # FUNCTION on_chat SHALL DEFINE PROCESS.
    def on_chat(self, handler: ChatHandler) -> Server:
        self._chat_handler = handler
        return self

    # FUNCTION on_message SHALL DEFINE PROCESS.
    def on_message(self, handler: MessageHandler) -> Server:
        self._msg_handler = handler
        return self

    # FUNCTION with_trug SHALL READ DATA.
    def with_trug(self, path: str | Path) -> Server:
        """Load a TRUG knowledge base from a JSON file (thin wrapper over
        ``JsonFileKnowledgeBaseStore`` for backwards compatibility)."""
        self.with_knowledge_base(JsonFileKnowledgeBaseStore(path))
        return self

    # FUNCTION with_llm SHALL DEFINE RECORD.
    def with_llm(self, provider: str, model: str, api_key_env: str) -> Server:
        self._llm_config = LLMConfig(provider=provider, model=model, api_key_env=api_key_env)
        return self

    # FUNCTION with_upstream SHALL DEFINE DATA.
    def with_upstream(self, addr: str, key: str) -> Server:
        self._upstream_addr = addr
        self._upstream_key = key
        return self

    # ── Store builders (the Protocol-backed surface) ─────────────────

    # FUNCTION with_guardrail_store SHALL DEFINE PROCESS.
    def with_guardrail_store(self, store: GuardrailStore) -> Server:
        """Inject a ``GuardrailStore`` implementation.

        <trl>
        FUNCTION with_guardrail_store SHALL DEFINE PROCESS store.
        </trl>
        """
        self._guardrail_store = store
        self._guardrails = list(store.guardrails())
        return self

    # FUNCTION with_response_store SHALL DEFINE PROCESS.
    def with_response_store(self, store: ResponseStore) -> Server:
        """Inject a ``ResponseStore`` implementation.

        <trl>
        FUNCTION with_response_store SHALL DEFINE PROCESS store.
        </trl>
        """
        self._response_store = store
        self._responses = list(store.responses())
        return self

    # FUNCTION with_banned_keys SHALL DEFINE PROCESS.
    def with_banned_keys(self, store: BannedKeyStore) -> Server:
        """Inject a ``BannedKeyStore`` implementation.

        <trl>
        FUNCTION with_banned_keys SHALL DEFINE PROCESS store.
        </trl>

        Example — persistent bans across restart::

            server.with_banned_keys(
                JsonFileBannedKeyStore("bans.json", ttl=timedelta(hours=72))
            )
        """
        self._banned_key_store = store
        return self

    # FUNCTION with_knowledge_base SHALL DEFINE PROCESS.
    def with_knowledge_base(self, store: KnowledgeBaseStore) -> Server:
        """Inject a ``KnowledgeBaseStore`` implementation.

        <trl>
        FUNCTION with_knowledge_base SHALL DEFINE PROCESS store.
        </trl>
        """
        self._knowledge_base_store = store
        self._trug_data = store.context()
        return self

    # ── Getters ──────────────────────────────────────────────────────

    # FUNCTION key SHALL RETURNS_TO SOURCE.
    def key(self) -> DHKey:
        return self._key

    # FUNCTION public_key SHALL RETURNS_TO SOURCE.
    def public_key(self) -> str:
        return key_to_hex(self._key.public)

    # FUNCTION get_trug_context SHALL RETURNS_TO SOURCE.
    def get_trug_context(self) -> str:
        return self._build_trug_context()

    # FUNCTION get_responses SHALL RETURNS_TO SOURCE.
    def get_responses(self) -> list[ResponseNode]:
        return self._responses

    def _build_trug_context(self) -> str:
        if self._trug_data is None:
            return ""
        nodes = self._trug_data.get("nodes")
        if not isinstance(nodes, list):
            return ""
        lines = ["Knowledge base:"]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            props = node.get("properties", {}) or {}
            name = props.get("name", "")
            desc = props.get("description", "")
            if isinstance(name, str) and name:
                lines.append(f"- {name}: {desc}")
        return "\n".join(lines) + "\n" if len(lines) > 1 else ""

    # ── Lifecycle ────────────────────────────────────────────────────

    # FUNCTION listen_and_serve SHALL RECEIVE DATA.
    def listen_and_serve(self) -> None:
        listener = listen(self._addr, self._key)
        self._listener = listener
        _log.info("Noise Chatbot listening on %s", self._addr)
        _log.info("Public key: %s", self.public_key())
        if self._responses:
            _log.info(
                "Template mode: %d response nodes loaded (LLM classifies, never composes)",
                len(self._responses),
            )

        def _handle_signal(_signum: int, _frame: object) -> None:
            _log.info("shutting down...")
            self._stop.set()
            listener.close()

        old_int = _signal.signal(_signal.SIGINT, _handle_signal)
        old_term = _signal.signal(_signal.SIGTERM, _handle_signal)
        try:
            self._accept_loop(listener)
        finally:
            _signal.signal(_signal.SIGINT, old_int)
            _signal.signal(_signal.SIGTERM, old_term)

    # FUNCTION serve_listener SHALL RECEIVE DATA.
    def serve_listener(self, listener: Listener) -> None:
        self._listener = listener
        self._accept_loop(listener)

    # FUNCTION stop SHALL REVOKE RESOURCE.
    def stop(self) -> None:
        self._stop.set()
        if self._listener is not None:
            self._listener.close()

    def _accept_loop(self, listener: Listener) -> None:
        while not self._stop.is_set():
            try:
                conn = listener.accept()
            except OSError:
                if self._stop.is_set():
                    return
                continue
            except Exception as exc:
                _log.warning("accept error: %s", exc)
                continue
            t = threading.Thread(target=self._serve_conn, args=(conn,), daemon=True)
            t.start()

    # ── Per-connection worker ────────────────────────────────────────

    def _serve_conn(self, conn: NoiseConn) -> None:
        try:
            self._serve_conn_body(conn)
        finally:
            conn.close()

    def _serve_conn_body(self, conn: NoiseConn) -> None:
        key_hex = key_to_hex(conn.remote_identity())
        if self._banned_key_store.is_banned(key_hex):
            return

        stats = ConnectionStats(connected_at=datetime.now())
        guardrail_hits = 0
        question_count = 0
        rate_lock = threading.Lock()
        message_timestamps: list[datetime] = []

        if self._safety.greeting:
            greeting = Message(
                type="CHAT",
                payload={"text": self._safety.greeting},
                id=str(uuid.uuid4()),
            )
            try:
                conn.send(greeting.to_json().encode("utf-8"))
            except Exception:
                return

        while not self._stop.is_set():
            if (
                self._safety.session_timeout.total_seconds() > 0
                and stats.last_message_at is not None
                and (datetime.now() - stats.last_message_at) > self._safety.session_timeout
            ):
                return

            try:
                raw = conn.receive()
            except (TimeoutError, ConnectionError, ValueError, RuntimeError, OSError):
                return
            except Exception:
                return

            if 0 < self._safety.max_input_bytes < len(raw):
                err = Message(
                    type="ERROR",
                    payload={"error": _ERR_TOO_LARGE},
                    id=str(uuid.uuid4()),
                )
                try:
                    conn.send(err.to_json().encode("utf-8"))
                except Exception:
                    return
                continue

            if self._safety.rate_limit > 0:
                with rate_lock:
                    now = datetime.now()
                    cutoff = now - timedelta(minutes=1)
                    message_timestamps[:] = [t for t in message_timestamps if t > cutoff]
                    message_timestamps.append(now)
                    over_limit = len(message_timestamps) > self._safety.rate_limit
                if over_limit:
                    err = Message(
                        type="ERROR",
                        payload={"error": _ERR_RATE_LIMIT},
                        id=str(uuid.uuid4()),
                    )
                    try:
                        conn.send(err.to_json().encode("utf-8"))
                    except Exception:
                        return
                    continue

            stats.messages_received += 1
            stats.last_message_at = datetime.now()

            try:
                msg = Message.from_json(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            if msg.type == "CHAT" and self._safety.max_input_tokens > 0:
                text = msg.payload.get("text", "") if isinstance(msg.payload, dict) else ""
                approx_tokens = len(text) // _TOKEN_CHARS_PER_TOKEN
                if approx_tokens > self._safety.max_input_tokens:
                    reply = Message(
                        type="CHAT",
                        payload={"text": _TEXT_TOKEN_CAP},
                        id=str(uuid.uuid4()),
                        reply_to=msg.id,
                    )
                    try:
                        conn.send(reply.to_json().encode("utf-8"))
                    except Exception:
                        return
                    continue

            resp, matched_nodes, hit_guardrail = self._handle_message_full(msg, question_count)

            for node_id in matched_nodes:
                stats.node_hits[node_id] = stats.node_hits.get(node_id, 0) + 1
            if not matched_nodes:
                stats.no_match_count += 1

            if msg.type == "CHAT":
                question_count += 1

            # Wind-down.
            if question_count >= _WIND_DOWN_START and not hit_guardrail and msg.type == "CHAT":
                extra = question_count - _WIND_DOWN_START
                delay = extra * _WIND_DOWN_PER_Q_DELAY_SECS
                if delay > 0:
                    time.sleep(delay)

                if question_count >= _WIND_DOWN_END:
                    farewell = Message(
                        type="CHAT",
                        payload={
                            "text": (
                                "Thank you for chatting with us today! I hope "
                                "I was able to help. For anything else, please "
                                "visit our website or contact our team "
                                "directly. Have a great day!"
                            )
                        },
                        id=str(uuid.uuid4()),
                        reply_to=msg.id,
                    )
                    try:
                        conn.send(farewell.to_json().encode("utf-8"))
                    finally:
                        self._banned_key_store.ban(key_hex)
                        _log.info(
                            "Temp-banned key %s for 3 days (40 questions reached)",
                            key_hex[:16],
                        )
                    return

                if question_count == _WIND_DOWN_START:
                    topics: list[str] = []
                    for node_id in stats.node_hits:
                        for node in self._responses:
                            if node.id == node_id and node.keywords:
                                topics.append(node.keywords[0])
                                break
                    summary_text = (
                        "We've covered a lot! Here's what we discussed: "
                        + (", ".join(topics) + ". " if topics else "")
                        + "You can find more detail on all of these on our website. "
                        "I'm still here if you have more questions!"
                    )
                    resp = Message(
                        type="CHAT",
                        payload={"text": summary_text},
                        id=str(uuid.uuid4()),
                        reply_to=msg.id,
                    )

            # Honeypot tier escalation.
            if hit_guardrail:
                guardrail_hits += 1
            if guardrail_hits >= _HONEYPOT_TIER2_HITS:
                if guardrail_hits >= _HONEYPOT_TIER4_HITS:
                    delay = _HONEYPOT_TIER4_DELAY_SECS
                elif guardrail_hits >= _HONEYPOT_TIER3_HITS:
                    delay = _HONEYPOT_TIER3_DELAY_SECS
                else:
                    delay = _HONEYPOT_TIER2_DELAY_SECS
                time.sleep(delay)

            if guardrail_hits >= _HONEYPOT_TIER5_HITS:
                farewell = Message(
                    type="CHAT",
                    payload={
                        "text": (
                            "Thank you for chatting with us today! It looks like "
                            "I've answered everything I can. Have a great day!"
                        )
                    },
                    id=str(uuid.uuid4()),
                    reply_to=msg.id,
                )
                try:
                    conn.send(farewell.to_json().encode("utf-8"))
                finally:
                    self._banned_key_store.ban(key_hex)
                    _log.info(
                        "Banned key %s (honeypot tier 5 \u2014 repeated probing)",
                        key_hex[:16],
                    )
                return

            if _HONEYPOT_TIER4_HITS <= guardrail_hits < _HONEYPOT_TIER5_HITS:
                pool = [
                    (
                        "Actually, let me check on that for you... I think "
                        "there might be something in our system. Can you be "
                        "more specific about what you need?"
                    ),
                    (
                        "Interesting question. I'm seeing some related "
                        "information but I need to verify. What exactly are "
                        "you looking for?"
                    ),
                    (
                        "I may have found something. Could you rephrase your "
                        "question so I can give you the right answer?"
                    ),
                    (
                        "Let me look into that further. In the meantime, is "
                        "there a specific part of our service you're asking "
                        "about?"
                    ),
                ]
                resp = Message(
                    type="CHAT",
                    payload={"text": pool[guardrail_hits % len(pool)]},
                    id=str(uuid.uuid4()),
                    reply_to=msg.id,
                )
            elif _HONEYPOT_TIER3_HITS <= guardrail_hits < _HONEYPOT_TIER4_HITS:
                pool = [
                    (
                        "Hmm, that's an interesting angle. I'm not sure I can "
                        "share that directly, but let me see what I can find..."
                    ),
                    (
                        "You're asking the right questions. Unfortunately my "
                        "access level doesn't cover that area. Have you tried "
                        "our help center?"
                    ),
                    (
                        "I think I understand what you're looking for. Let me "
                        "check if there's a public resource for that..."
                    ),
                ]
                resp = Message(
                    type="CHAT",
                    payload={"text": pool[guardrail_hits % len(pool)]},
                    id=str(uuid.uuid4()),
                    reply_to=msg.id,
                )
            elif _HONEYPOT_TIER2_HITS <= guardrail_hits < _HONEYPOT_TIER3_HITS:
                pool = [
                    (
                        "I appreciate your patience. That's outside my current "
                        "scope, but I'm happy to help with product questions."
                    ),
                    (
                        "Good question \u2014 unfortunately that falls under "
                        "a different department. Can I help with something "
                        "else?"
                    ),
                    (
                        "I've noted your request. For that type of inquiry, "
                        "our team would need to assist you directly."
                    ),
                ]
                resp = Message(
                    type="CHAT",
                    payload={"text": pool[guardrail_hits % len(pool)]},
                    id=str(uuid.uuid4()),
                    reply_to=msg.id,
                )

            if self._on_analytics is not None:
                user_text = msg.payload.get("text", "") if isinstance(msg.payload, dict) else ""
                self._on_analytics(stats, user_text, matched_nodes)

            try:
                conn.send(resp.to_json().encode("utf-8"))
            except Exception:
                return

    # ── Routing ──────────────────────────────────────────────────────

    def _handle_message_full(
        self, msg: Message, question_count: int
    ) -> tuple[Message, list[str], bool]:
        """Core routing. Returns (response, matched_ids, hit_guardrail)."""
        from noise_chatbot.server.classifier import default_classifier

        if self._msg_handler is not None:
            return self._msg_handler(msg), [], False

        if msg.type == "CHAT":
            user_text = msg.payload.get("text", "") if isinstance(msg.payload, dict) else ""
            classify = self._classifier or default_classifier
            response_text = ""
            matched_nodes: list[str] = []
            hit_guardrail = False

            if self._guardrails:
                guard_ids = classify(user_text, self._guardrails)
                if guard_ids:
                    hit_guardrail = True
                    matched_nodes = guard_ids
                    for node in self._guardrails:
                        if node.id == guard_ids[0]:
                            response_text = node.response
                            break

            if not response_text and self._responses:
                node_ids = classify(user_text, self._responses)
                if (
                    not node_ids
                    and self._fallback_classifier is not None
                    and question_count <= _WIND_DOWN_START
                ):
                    node_ids = self._fallback_classifier(user_text, self._responses)
                if len(node_ids) > _MATCH_CAP:
                    node_ids = node_ids[:_MATCH_CAP]
                matched_nodes = node_ids

                if not node_ids:
                    response_text = self._no_match_text
                else:
                    response_index = {n.id: n.response for n in self._responses}
                    parts = [response_index[i] for i in node_ids if i in response_index]
                    response_text = "\n\n".join(parts) if parts else self._no_match_text
            elif not response_text and self._chat_handler is not None:
                response_text = self._chat_handler(user_text)
            elif not response_text:
                response_text = user_text

            formatted = response_text
            if question_count > 0:
                formatted = f"You asked about: {user_text}\n\n{response_text}"
            if self._contact_footer:
                formatted += f"\n\n{self._contact_footer}"
            if question_count > 0:
                formatted += f"\n\n({question_count})"

            return (
                Message(
                    type="CHAT",
                    payload={"text": formatted},
                    id=str(uuid.uuid4()),
                    reply_to=msg.id,
                ),
                matched_nodes,
                hit_guardrail,
            )

        return (
            Message(
                type=msg.type,
                payload=msg.payload,
                id=str(uuid.uuid4()),
                reply_to=msg.id,
            ),
            [],
            False,
        )
