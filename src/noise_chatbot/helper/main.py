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
import sys


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

    Go parity: ``helper/main.go``. The reader thread treats ``EOF`` as a
    clean exit (``sys.exit(0)``); setup/send failures exit with 1.
    """
    parser = argparse.ArgumentParser(
        prog="noise-helper",
        description="stdin/stdout Noise_IK bridge for non-Python clients.",
    )
    parser.add_argument(
        "--server",
        default="localhost:9090",
        help="server address (host:port); default localhost:9090",
    )
    parser.add_argument(
        "--key",
        required=True,
        help="server public key (hex)",
    )
    parser.parse_args(argv)

    # Phase C implements the handshake + goroutine loop.
    sys.stderr.write("ERROR: noise-helper not implemented (Phase B scaffold — Phase C fills)\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
