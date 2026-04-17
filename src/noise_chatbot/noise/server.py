"""Noise_IK server-side listener + responder handshake.

<trl>
MODULE noise CONTAINS FUNCTION listen AND RECORD Listener AND FUNCTION server_handshake.
FUNCTION listen SHALL DEFINE RESOURCE Listener AT ENDPOINT addr BINDS RECORD server_key.
</trl>
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_chatbot.noise.conn import NoiseConn
    from noise_chatbot.noise.keys import DHKey


@dataclass(slots=True)
class Listener:
    """Wraps a TCP listen socket plus the server's static keypair.

    <trl>
    DEFINE RECORD Listener CONTAINS RESOURCE inner AND RECORD server_key.
    </trl>

    Go parity: ``noise.Listener``.
    """

    inner: socket.socket
    server_key: DHKey

    def accept(self) -> NoiseConn:
        """Block until a client connects, perform the responder handshake.

        <trl>
        FUNCTION Listener.accept SHALL RECEIVE RESOURCE conn FROM RESOURCE Listener
            THEN AUTHENTICATE PARTY client BY FUNCTION server_handshake.
        FUNCTION Listener.accept SHALL REVOKE RESOURCE conn IF FUNCTION server_handshake 'is FAILED.
        </trl>

        Go parity:
            ``(*Listener).Accept`` — error ``"accept: %w"``.
        """
        raise NotImplementedError("Phase C")

    def close(self) -> None:
        """Close the listen socket.

        <trl>FUNCTION Listener.close SHALL REVOKE RESOURCE Listener.</trl>
        """
        raise NotImplementedError("Phase C")

    def addr(self) -> tuple[str, int]:
        """Return the bound ``(host, port)``.

        <trl>FUNCTION Listener.addr SHALL RETURNS_TO SOURCE ENDPOINT addr.</trl>
        """
        raise NotImplementedError("Phase C")


def listen(addr: str, server_key: DHKey) -> Listener:
    """Start a TCP listener bound to the server's static key.

    <trl>
    FUNCTION listen SHALL DEFINE RESOURCE Listener AT ENDPOINT addr
        BINDS RECORD server_key THEN RETURNS_TO SOURCE.
    </trl>

    Go parity: ``noise.Listen`` — error ``"listen: %w"``.
    """
    raise NotImplementedError("Phase C")


def server_handshake(conn: socket.socket, server_key: DHKey) -> NoiseConn:
    """Perform the Noise_IK responder handshake, extract client's static pubkey.

    <trl>
    FUNCTION server_handshake SHALL DEFINE DATA handshake AS RESPONDER
        BINDS RECORD server_key.
    FUNCTION server_handshake SHALL READ DATA msg1 FROM RESOURCE conn
        THEN WRITE DATA msg2 TO RESOURCE conn
        THEN MAP DATA handshake AS STRING client_pub
        THEN RETURNS_TO SOURCE RECORD NoiseConn.
    </trl>

    Go parity: ``noise.ServerHandshake``.
    """
    raise NotImplementedError("Phase C")
