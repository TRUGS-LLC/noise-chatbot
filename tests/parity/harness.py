"""Python parity test harness.

<trl>
PROCESS harness SHALL READ RECORD config FROM ENTRY stdin THEN DEFINE SERVICE Server
    THEN WRITE STRING READY AND ENDPOINT host_port AND STRING pubkey TO EXIT stdout.
</trl>

Mirrors ``REFERENCE/parity/harness/main.go`` from the Go parity corpus so the
YAML fixtures run without modification against the Python stack.

Protocol:
    1. Reads JSON configuration on stdin (see ``Config`` below).
    2. Starts a ``noise_chatbot.server.Server`` on an ephemeral port.
    3. Prints exactly one line to stdout: ``READY host:port pubkey_hex``.
    4. Blocks on ``serve_listener`` until SIGINT / SIGTERM.
"""

from __future__ import annotations

import contextlib
import json
import signal
import sys
import threading
from datetime import timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from noise_chatbot.noise.server import listen
from noise_chatbot.server import ResponseNode, SafetyConfig, Server


def _node_from_config(entry: dict[str, Any]) -> ResponseNode:
    return ResponseNode(
        id=entry.get("id", ""),
        keywords=list(entry.get("keywords", [])),
        response=entry.get("response", ""),
    )


def _write_temp_guardrail_trug(nodes: list[ResponseNode]) -> str:
    """Serialise ``nodes`` as a minimal guardrails.trug.json for WithGuardrails."""
    payload = {
        "nodes": [
            {
                "id": n.id,
                "properties": {"keywords": n.keywords, "response": n.response},
            }
            for n in nodes
        ]
    }
    with NamedTemporaryFile(mode="w", suffix=".trug.json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f)
        return f.name


def main() -> int:
    raw = sys.stdin.read()
    cfg: dict[str, Any] = json.loads(raw) if raw.strip() else {}

    addr = cfg.get("addr") or "127.0.0.1:0"
    s = Server(addr)

    # Safety overrides — match Go harness semantics.
    raw_safety = bool(cfg.get("raw_safety"))
    has_safety_override = any(
        cfg.get(k)
        for k in (
            "max_input_tokens",
            "max_input_bytes",
            "rate_limit",
            "session_timeout_seconds",
        )
    )
    if raw_safety:
        s.with_safety(
            SafetyConfig(
                max_input_tokens=int(cfg.get("max_input_tokens", 0)),
                max_input_bytes=int(cfg.get("max_input_bytes", 0)),
                rate_limit=int(cfg.get("rate_limit", 0)),
                session_timeout=timedelta(seconds=int(cfg.get("session_timeout_seconds", 0))),
            )
        )
    elif has_safety_override:
        safety = SafetyConfig()
        if cfg.get("max_input_tokens"):
            safety.max_input_tokens = int(cfg["max_input_tokens"])
        if cfg.get("max_input_bytes"):
            safety.max_input_bytes = int(cfg["max_input_bytes"])
        if cfg.get("rate_limit"):
            safety.rate_limit = int(cfg["rate_limit"])
        if cfg.get("session_timeout_seconds"):
            safety.session_timeout = timedelta(seconds=int(cfg["session_timeout_seconds"]))
        s.with_safety(safety)

    extra_guardrails = cfg.get("extra_guardrails")
    if extra_guardrails:
        nodes = [_node_from_config(e) for e in extra_guardrails]
        path = _write_temp_guardrail_trug(nodes)
        s.with_guardrails(path)

    if cfg.get("responses"):
        s.with_responses([_node_from_config(e) for e in cfg["responses"]])

    if cfg.get("no_match_text"):
        s.with_no_match(cfg["no_match_text"])

    if cfg.get("greeting"):
        s.with_greeting(cfg["greeting"])

    if cfg.get("contact_footer"):
        s.with_contact_footer(cfg["contact_footer"])

    handler_kind = cfg.get("chat_handler", "")
    if handler_kind == "echo":
        s.on_chat(lambda text: "You said: " + text)
    elif handler_kind == "prefix":
        prefix = cfg.get("prefix_text", "")
        s.on_chat(lambda text: prefix + text)

    listener = listen(addr, s.key())
    _host, port = listener.addr()
    sys.stdout.write(f"READY 127.0.0.1:{port} {s.public_key()}\n")
    sys.stdout.flush()

    stopped = threading.Event()

    def _shutdown(_signum: int, _frame: object) -> None:
        stopped.set()
        s.stop()
        listener.close()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        s.serve_listener(listener)
    except Exception:
        return 1
    finally:
        with contextlib.suppress(Exception):
            _cleanup_temp_files()
    return 0


_TEMP_FILES: list[str] = []


def _cleanup_temp_files() -> None:
    for path in _TEMP_FILES:
        with contextlib.suppress(OSError):
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
