"""noise-helper CLI entry point — stdin/stdout Noise_IK bridge.

<trl>
DEFINE INTERFACE noise_helper CONTAINS ENTRY stdin AND EXIT stdout AND EXIT stderr.
PROCESS helper SHALL REJECT ENTRY IF STRING flag_key EQUALS NONE.
</trl>

CLI surface (Go parity):
    noise-helper --server HOST:PORT --key HEX

    --server  default "localhost:9090"
    --key     required; Curve25519 public key as hex

stdout:
    "CONNECTED"            — printed on successful handshake
    raw decrypted bytes\\n — one line per server message

stderr:
    "ERROR: ..."           — setup/send/recv failures

Exit codes:
    0  — clean EOF (server disconnected normally)
    1  — setup or send error, missing --key
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading

from noise_chatbot.noise.keys import generate_keypair, hex_to_key
from noise_chatbot.noise.tcp_client import dial


def main(argv: list[str] | None = None) -> int:
    """Parse flags, handshake, spawn reader thread, run stdin→server loop.

    <trl>
    PROCESS helper SHALL READ STRING json FROM ENTRY stdin
        THEN VALIDATE STRING json AS JSON
        THEN SEND STRING json TO ENDPOINT server FOR EACH STRING json.
    PROCESS helper SHALL DEFINE PROCESS reader PARALLEL
        'that SHALL RECEIVE DATA FROM ENDPOINT server
        THEN WRITE RESULT TO EXIT stdout UNTIL EXCEPTION.
    </trl>
    """
    parser = argparse.ArgumentParser(
        prog="noise-helper",
        description="stdin/stdout Noise_IK bridge.",
    )
    parser.add_argument("--server", default="localhost:9090", help="server address (host:port)")
    parser.add_argument("--key", default="", help="server public key (hex)")
    args = parser.parse_args(argv)

    if not args.key:
        sys.stderr.write("ERROR: --key required\n")
        return 1

    try:
        server_pub = hex_to_key(args.key)
    except ValueError as exc:
        sys.stderr.write(f"ERROR: invalid key: {exc}\n")
        return 1

    try:
        client_key = generate_keypair()
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"ERROR: keygen: {exc}\n")
        return 1

    try:
        conn = dial(args.server, client_key, server_pub)
    except Exception as exc:
        sys.stderr.write(f"ERROR: connect: {exc}\n")
        return 1

    sys.stdout.write("CONNECTED\n")
    sys.stdout.flush()

    def _reader() -> None:
        """Receive → stdout. ``os._exit(0)`` on EOF/recv error (Go parity)."""
        while True:
            try:
                data = conn.receive()
            except Exception as exc:
                sys.stderr.write(f"ERROR: recv: {exc}\n")
                os._exit(0)
            try:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.write(b"\n")
                sys.stdout.buffer.flush()
            except Exception:
                os._exit(0)

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    # Main loop: stdin → server. One JSON message per line, skip empties,
    # validate JSON before sending.
    try:
        for raw_line in sys.stdin:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError:
                sys.stderr.write("ERROR: invalid JSON on stdin\n")
                continue
            try:
                conn.send(line.encode("utf-8"))
            except Exception as exc:
                sys.stderr.write(f"ERROR: send: {exc}\n")
                return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    raise SystemExit(main())
