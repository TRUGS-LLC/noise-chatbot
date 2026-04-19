"""Unit tests for length-prefixed handshake frame I/O.

<trl>
STAGE test_frame SHALL VALIDATE FUNCTION write_frame AND FUNCTION read_frame
    SUBJECT_TO RECORD fake_socket.
EACH RECORD frame SHALL CONTAIN INTEGER length AND DATA payload.
</trl>

Uses an in-memory fake socket to avoid real networking — the functions
under test only need ``sendall`` and ``recv``.
"""

from __future__ import annotations

import socket
import struct
from typing import cast

import pytest

from noise_chatbot.noise.frame import read_frame, write_frame


# AGENT fakesocket SHALL DEFINE RESOURCE.
class FakeSocket:
    """Minimal socket double for frame I/O.

    <trl>
    RECORD fakesocket SHALL BUFFER DATA outbox AND DATA inbox.
    FUNCTION sendall SHALL WRITE DATA TO DATA outbox.
    FUNCTION recv SHALL READ DATA FROM DATA inbox.
    </trl>

    ``_outbox`` captures bytes written via ``sendall``; ``_inbox`` feeds bytes
    to ``recv``. Chunking is handled so ``recv`` can return short reads.
    """

    def __init__(self, inbox: bytes = b"") -> None:
        self._outbox = bytearray()
        self._inbox = bytearray(inbox)

    # FUNCTION sendall SHALL WRITE DATA.
    def sendall(self, data: bytes) -> None:
        self._outbox.extend(data)

    # FUNCTION recv SHALL RECEIVE DATA.
    def recv(self, n: int) -> bytes:
        if not self._inbox:
            return b""
        chunk = bytes(self._inbox[:n])
        del self._inbox[:n]
        return chunk


def _sock(s: FakeSocket) -> socket.socket:
    """Type-level cast: our duck-typed FakeSocket satisfies the subset of
    ``socket.socket`` that ``read_frame`` / ``write_frame`` actually use."""
    return cast(socket.socket, s)


# AGENT SHALL VALIDATE PROCESS write_frame_prefixes_big_endian_length.
def test_write_frame_prefixes_big_endian_length() -> None:
    """``write_frame`` writes a 4-byte big-endian length followed by data."""
    s = FakeSocket()
    write_frame(_sock(s), b"hello")
    assert s._outbox == struct.pack(">I", 5) + b"hello"


# AGENT SHALL VALIDATE PROCESS write_frame_empty_payload.
def test_write_frame_empty_payload() -> None:
    """Empty payload still writes a length prefix of 0."""
    s = FakeSocket()
    write_frame(_sock(s), b"")
    assert s._outbox == struct.pack(">I", 0)


# AGENT SHALL VALIDATE PROCESS read_frame_decodes_length_and_data.
def test_read_frame_decodes_length_and_data() -> None:
    """``read_frame`` consumes 4-byte length + payload and returns payload."""
    payload = b"frame contents"
    s = FakeSocket(inbox=struct.pack(">I", len(payload)) + payload)
    assert read_frame(_sock(s)) == payload


# AGENT SHALL VALIDATE PROCESS read_frame_rejects_oversize.
def test_read_frame_rejects_oversize() -> None:
    """Length > 65 536 raises ``ValueError`` (handshake frame cap)."""
    s = FakeSocket(inbox=struct.pack(">I", 65_537))
    with pytest.raises(ValueError, match="frame too large"):
        read_frame(_sock(s))


# AGENT SHALL VALIDATE PROCESS read_frame_short_read_raises.
def test_read_frame_short_read_raises() -> None:
    """Peer close mid-length-prefix raises ``ConnectionError``."""
    s = FakeSocket(inbox=b"\x00\x00")  # only 2 of 4 length bytes
    with pytest.raises(ConnectionError, match="short read"):
        read_frame(_sock(s))


# AGENT SHALL VALIDATE PROCESS write_then_read_round_trip.
def test_write_then_read_round_trip() -> None:
    """A frame written by ``write_frame`` is parseable by ``read_frame``."""
    s = FakeSocket()
    payload = b"\x01\x02\x03\xff"
    write_frame(_sock(s), payload)
    # Feed the outbox back as inbox and read.
    s._inbox = bytearray(s._outbox)
    s._outbox.clear()
    assert read_frame(_sock(s)) == payload
