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

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_chatbot.noise.keys import DHKey
    from noise_chatbot.noise.server import Listener
    from noise_chatbot.protocol.message import Message
    from noise_chatbot.server.classifier import Classifier


# <trl>
# DEFINE FUNCTION ChatHandler SHALL MAP STRING text AS STRING response.
# AGENT claude SHALL DEPRECATE FUNCTION ChatHandler.
# </trl>
ChatHandler = Callable[[str], str]
"""DEPRECATED: legacy free-text chat handler.

Allows the handler to return arbitrary text — the LLM could hallucinate.
Use ``(*Server).with_responses`` + ``with_classifier`` for safe
template-only responses where the LLM classifies but never composes.
"""

# <trl>DEFINE FUNCTION MessageHandler SHALL MAP RECORD Message AS RECORD Message.</trl>
MessageHandler = Callable[["Message"], "Message"]
"""Full-message handler; takes priority over all CHAT routing when set."""


@dataclass(slots=True)
class ResponseNode:
    """A pre-authored response — ID, keywords, verbatim text.

    <trl>
    DEFINE RECORD ResponseNode CONTAINS STRING id AND ARRAY keywords AND STRING response.
    </trl>

    Go parity: ``server.ResponseNode``.
    """

    id: str
    keywords: list[str]
    response: str


@dataclass(slots=True)
class SafetyConfig:
    """Per-server safety knobs.

    <trl>
    DEFINE RECORD SafetyConfig CONTAINS INTEGER max_input_tokens
        AND INTEGER max_input_bytes AND INTEGER rate_limit
        AND INTEGER session_timeout AND STRING greeting AND INTEGER confidence_min.
    </trl>

    All integer fields: 0 = unlimited. Defaults (from ``Server.__init__``):
        max_input_tokens = 200, max_input_bytes = 2000, rate_limit = 30,
        session_timeout = 30 minutes, confidence_min = 1.

    Go parity: ``server.SafetyConfig``.
    """

    max_input_tokens: int = 200
    max_input_bytes: int = 2000
    rate_limit: int = 30
    session_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    greeting: str = ""
    confidence_min: int = 1


@dataclass(slots=True)
class ConnectionStats:
    """Per-connection analytics counters.

    <trl>
    DEFINE RECORD ConnectionStats CONTAINS INTEGER messages_received
        AND OBJECT node_hits AND INTEGER no_match_count
        AND DATA connected_at AND DATA last_message_at.
    </trl>
    """

    messages_received: int = 0
    node_hits: dict[str, int] = field(default_factory=dict)
    no_match_count: int = 0
    connected_at: datetime | None = None
    last_message_at: datetime | None = None


@dataclass(slots=True)
class LLMConfig:
    """LLM classifier configuration — stored, not auto-wired.

    <trl>
    DEFINE RECORD LLMConfig CONTAINS STRING provider AND STRING model AND STRING api_key_env.
    </trl>

    Stores the provider name (``"anthropic"`` / ``"openai"``), the model
    identifier, and the environment variable name holding the API key.
    The caller must pair this with ``with_classifier`` or
    ``with_fallback_classifier`` — the config alone does NOT install a
    classifier (Go parity: same no-op behaviour, tagged ``[STUB]`` in
    the super-TRUG).
    """

    provider: str
    model: str
    api_key_env: str


# <trl>
# Analytics callback signature: (stats, user_text, matched_node_ids) -> None.
# </trl>
AnalyticsCallback = Callable[[ConnectionStats, str, list[str]], None]


class Server:
    """Encrypted chatbot server — template mode + honeypot + wind-down.

    <trl>
    DEFINE SERVICE Server AT ENDPOINT addr THEN BIND RECORD key BY FUNCTION generate_keypair
        THEN BIND RECORD safety AS DEFAULT
        THEN BIND ARRAY guardrails AS RESOURCE DEFAULT_GUARDRAILS.
    </trl>

    Two modes:
        - **Template mode (safe)**: LLM classifies user input → picks a
          ResponseNode ID → returns verbatim text. Set up via
          ``with_responses`` + ``with_classifier``.
        - **Handler mode (legacy)**: ``on_chat`` callback returns
          arbitrary text. DEPRECATED — allows LLM to compose.

    Go parity: ``server.Server``. All builder methods return ``self`` for
    chaining (``builder_chain: true`` in the super-TRUG).
    """

    def __init__(self, addr: str) -> None:
        """Create a new Server at ``addr`` with safe defaults.

        <trl>
        FUNCTION New SHALL DEFINE SERVICE Server AT ENDPOINT addr
            THEN BIND RECORD key BY FUNCTION generate_keypair
            THEN BIND RECORD safety AS DEFAULT
            THEN BIND ARRAY guardrails AS RESOURCE DEFAULT_GUARDRAILS
            THEN RETURNS_TO SOURCE.
        </trl>

        Defaults:
            - fresh Curve25519 static keypair via ``noise.generate_keypair``
            - ``SafetyConfig()`` with Go defaults (200/2000/30/30min/1)
            - ``DEFAULT_GUARDRAILS`` loaded (copy, so tests can mutate)
            - ``no_match_text = "I don't have information about that. Please contact us directly."``

        Go parity: ``server.New``.
        """
        raise NotImplementedError("Phase C")

    # ── Builder methods (each returns self) ──────────────────────────

    def with_safety(self, cfg: SafetyConfig) -> Server:
        """Replace the full safety config.

        <trl>FUNCTION with_safety SHALL REPLACE RECORD safety ON SELF BY RECORD cfg THEN RETURNS_TO SOURCE SELF.</trl>
        """
        raise NotImplementedError("Phase C")

    def with_greeting(self, text: str) -> Server:
        """Set the first message sent on client connect.

        <trl>FUNCTION with_greeting SHALL REPLACE STRING greeting ON RECORD safety BY STRING text.</trl>
        """
        raise NotImplementedError("Phase C")

    def with_guardrails(self, path: str | Path) -> Server:
        """Append guardrail nodes from a .trug.json file.

        <trl>
        FUNCTION with_guardrails SHALL READ FILE path THEN MAP DATA json AS ARRAY nodes
            THEN AUGMENT ARRAY guardrails ON SELF BY ARRAY nodes.
        FUNCTION with_guardrails SHALL HANDLE EXCEPTION BY WRITE STRING warning TO EXIT log
            THEN RETURNS_TO SOURCE SELF.
        </trl>

        Note: additive, not replacing. Default 15 guardrails remain in place.
        On read/parse failure, logs a warning and returns self unchanged.
        """
        raise NotImplementedError("Phase C")

    def on_analytics(self, fn: AnalyticsCallback) -> Server:
        """Install an analytics callback invoked on every CHAT message.

        <trl>FUNCTION on_analytics SHALL REPLACE FUNCTION on_analytics ON SELF BY FUNCTION fn.</trl>
        """
        raise NotImplementedError("Phase C")

    def with_responses(self, nodes: list[ResponseNode]) -> Server:
        """Replace the business-response node list.

        <trl>FUNCTION with_responses SHALL REPLACE ARRAY responses ON SELF BY ARRAY nodes.</trl>
        """
        raise NotImplementedError("Phase C")

    def with_responses_from_trug(self, path: str | Path) -> Server:
        """Load response nodes from a .trug.json file.

        <trl>
        FUNCTION with_responses_from_trug SHALL READ FILE path THEN MAP DATA json AS ARRAY nodes
            THEN FILTER ARRAY nodes BY STRING response EXISTS
            THEN REPLACE ARRAY responses ON SELF BY RESULT.
        </trl>

        For each node: ``properties.response`` (or ``properties.description``
        as fallback) becomes the response text; ``properties.keywords[]``
        plus ``properties.name`` become keywords.
        """
        raise NotImplementedError("Phase C")

    def with_classifier(self, classifier: Classifier) -> Server:
        """Replace the default keyword classifier.

        <trl>FUNCTION with_classifier SHALL REPLACE FUNCTION classifier ON SELF BY FUNCTION classifier.</trl>
        """
        raise NotImplementedError("Phase C")

    def with_fallback_classifier(self, classifier: Classifier) -> Server:
        """Install an LLM-backed fallback classifier.

        <trl>
        FUNCTION with_fallback_classifier SHALL REPLACE FUNCTION fallback_classifier ON SELF.
        SERVICE Server MAY MAP STRING user_text BY FUNCTION fallback_classifier
            IF ARRAY ids EQUALS NONE AND INTEGER question_count NOT EXCEEDS 20.
        </trl>

        Only invoked when the primary classifier returns empty AND
        ``question_count <= 20`` (zero API cost after 20 for abusive
        sessions).
        """
        raise NotImplementedError("Phase C")

    def with_no_match(self, text: str) -> Server:
        """Set the text returned when no classifier match is found.

        <trl>FUNCTION with_no_match SHALL REPLACE STRING no_match_text ON SELF BY STRING text.</trl>
        """
        raise NotImplementedError("Phase C")

    def with_contact_footer(self, footer: str) -> Server:
        """Append contact info (email/phone/URL) to every response.

        <trl>FUNCTION with_contact_footer SHALL REPLACE STRING contact_footer ON SELF BY STRING footer.</trl>
        """
        raise NotImplementedError("Phase C")

    def on_chat(self, handler: ChatHandler) -> Server:
        """DEPRECATED: install a legacy free-text CHAT handler.

        <trl>
        FUNCTION on_chat SHALL REPLACE FUNCTION chat_handler ON SELF BY FUNCTION handler.
        AGENT claude SHALL DEPRECATE FUNCTION on_chat.
        </trl>
        """
        raise NotImplementedError("Phase C")

    def on_message(self, handler: MessageHandler) -> Server:
        """Install a full-message handler; takes priority over all CHAT routing.

        <trl>
        FUNCTION on_message SHALL REPLACE FUNCTION msg_handler ON SELF BY FUNCTION handler.
        SERVICE Server SHALL ROUTE EACH RECORD Message TO FUNCTION msg_handler IF FUNCTION msg_handler EXISTS.
        </trl>
        """
        raise NotImplementedError("Phase C")

    def with_trug(self, path: str | Path) -> Server:
        """Load a .trug.json as read-only chatbot context.

        <trl>FUNCTION with_trug SHALL READ FILE path AS READONLY THEN REPLACE DATA trug_data ON SELF.</trl>
        """
        raise NotImplementedError("Phase C")

    def with_llm(self, provider: str, model: str, api_key_env: str) -> Server:
        """Store LLM configuration. Does NOT wire a classifier by itself.

        <trl>
        FUNCTION with_llm SHALL DEFINE RECORD LLMConfig CONTAINS STRING provider
            AND STRING model AND STRING api_key_env
            THEN REPLACE RECORD llm_config ON SELF BY RECORD LLMConfig.
        </trl>

        Caller must pair with ``with_classifier`` or
        ``with_fallback_classifier``.
        """
        raise NotImplementedError("Phase C")

    def with_upstream(self, addr: str, key: str) -> Server:
        """Store upstream gateway address + key (Phase D feature — ``[STUB]``).

        <trl>FUNCTION with_upstream SHALL REPLACE STRING upstream_addr ON SELF.</trl>

        In the Go parity: the fields are stored but never read. Preserved
        here for source-level parity; functional behaviour is deferred.
        """
        raise NotImplementedError("Phase C")

    # ── Getters ──────────────────────────────────────────────────────

    def key(self) -> DHKey:
        """Return the full server keypair (useful for tests).

        <trl>FUNCTION key SHALL RETURNS_TO SOURCE RECORD key.</trl>
        """
        raise NotImplementedError("Phase C")

    def public_key(self) -> str:
        """Return the server's public key as hex.

        <trl>FUNCTION public_key SHALL MAP STRING public FROM RECORD key AS STRING hex.</trl>
        """
        raise NotImplementedError("Phase C")

    def get_trug_context(self) -> str:
        """Return a text summary of loaded TRUG context data.

        <trl>FUNCTION get_trug_context SHALL MAP DATA trug_data AS STRING summary.</trl>
        """
        raise NotImplementedError("Phase C")

    def get_responses(self) -> list[ResponseNode]:
        """Return the currently loaded response-node list.

        <trl>FUNCTION get_responses SHALL RETURNS_TO SOURCE ARRAY responses.</trl>
        """
        raise NotImplementedError("Phase C")

    # ── Lifecycle ────────────────────────────────────────────────────

    def listen_and_serve(self) -> None:
        """Start the listener, install SIGINT/SIGTERM handlers, block until shutdown.

        <trl>
        FUNCTION listen_and_serve SHALL DEFINE RESOURCE listener BY FUNCTION noise.listen
            AT ENDPOINT addr BINDS RECORD key.
        FUNCTION listen_and_serve SHALL DEFINE PROCESS signal_handler PARALLEL
            'that SHALL RECEIVE STREAM sig_ch THEN REVOKE RESOURCE listener.
        FUNCTION listen_and_serve SHALL ROUTE EACH RESOURCE conn FROM RESOURCE listener
            TO PROCESS serve_conn PARALLEL.
        </trl>

        Signals handled: ``SIGINT``, ``SIGTERM`` (Go parity).

        Go parity: ``(*Server).ListenAndServe``.
        """
        raise NotImplementedError("Phase C")

    def serve_listener(self, listener: Listener) -> None:
        """Serve on an existing Listener; close it when the context is cancelled.

        <trl>
        FUNCTION serve_listener SHALL DEFINE PROCESS ctx_closer PARALLEL
            'that SHALL REVOKE RESOURCE listener WHEN STREAM ctx EXPIRES.
        FUNCTION serve_listener SHALL ROUTE EACH RESOURCE conn FROM RESOURCE listener
            TO PROCESS serve_conn PARALLEL.
        </trl>

        Go parity: ``(*Server).ServeListener`` — used by tests and the
        parity harness so the bound port can be observed before the
        accept loop starts.
        """
        raise NotImplementedError("Phase C")
