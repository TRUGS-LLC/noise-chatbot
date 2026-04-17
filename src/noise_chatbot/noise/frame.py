"""Length-prefixed frame I/O for Noise handshake messages.

<trl>
MODULE noise CONTAINS FUNCTION write_frame AND FUNCTION read_frame.
EACH RECORD frame SHALL CONTAIN INTEGER length AND DATA payload.
</trl>
"""

from __future__ import annotations

import socket

# <trl>DEFINE INTEGER handshake_frame_max_bytes AS 65536.</trl>
HANDSHAKE_FRAME_MAX_BYTES: int = 65_536


def write_frame(conn: socket.socket, data: bytes) -> None:
    """Write a 4-byte big-endian length prefix followed by ``data`` to ``conn``.

    <trl>
    FUNCTION write_frame SHALL WRITE INTEGER length AND DATA data TO RESOURCE conn.
    </trl>

    Go parity:
        ``noise/frame.go:writeFrame`` — ``binary.BigEndian`` uint32 prefix.
    """
    raise NotImplementedError("Phase C")


def read_frame(conn: socket.socket) -> bytes:
    """Read a length-prefixed frame; reject frames over 65 536 bytes.

    <trl>
    FUNCTION read_frame SHALL READ INTEGER length FROM RESOURCE conn
        THEN REJECT IF INTEGER length EXCEEDS 65536.
    FUNCTION read_frame SHALL READ DATA data FROM RESOURCE conn THEN RETURNS_TO SOURCE.
    </trl>

    Raises:
        ValueError: If the length prefix exceeds 65 536.
        OSError: On socket read failure (propagated).

    Go parity:
        ``noise/frame.go:readFrame`` — cap at 65 536.
    """
    raise NotImplementedError("Phase C")
