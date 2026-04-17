"""Noise_IK client-side dial + handshake.

<trl>
MODULE noise CONTAINS FUNCTION dial AND FUNCTION client_handshake.
FUNCTION dial SHALL AUTHENTICATE PARTY client SUBJECT_TO STRING server_pub_key.
</trl>

Module named ``tcp_client`` (not ``client``) to avoid shadowing the top-level
``noise_chatbot.client`` public API package.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_chatbot.noise.conn import NoiseConn
    from noise_chatbot.noise.keys import DHKey


def dial(addr: str, client_key: DHKey, server_pub_key: bytes) -> NoiseConn:
    """TCP-dial ``addr`` then perform the Noise_IK initiator handshake.

    <trl>
    FUNCTION dial SHALL REQUEST RESOURCE conn FROM ENDPOINT addr
        THEN AUTHENTICATE RECORD client_key SUBJECT_TO STRING server_pub_key
        BY FUNCTION client_handshake.
    FUNCTION dial SHALL REVOKE RESOURCE conn IF FUNCTION client_handshake 'is FAILED.
    </trl>

    Args:
        addr: ``"host:port"``.
        client_key: Client's own static keypair.
        server_pub_key: 32-byte Curve25519 public key of the server
            (known out-of-band per Noise_IK assumptions).

    Returns:
        An established ``NoiseConn``.

    Raises:
        OSError: TCP dial failure.
        RuntimeError: Handshake failure (raw socket closed before raising).

    Go parity:
        ``noise.Dial`` — net.Dial + ClientHandshake.
    """
    raise NotImplementedError("Phase C")


def client_handshake(conn: socket.socket, client_key: DHKey, server_pub_key: bytes) -> NoiseConn:
    """Perform the Noise_IK initiator handshake on an already-connected socket.

    <trl>
    FUNCTION client_handshake SHALL DEFINE DATA handshake AS INITIATOR
        SUBJECT_TO STRING server_pub_key.
    FUNCTION client_handshake SHALL WRITE DATA msg1 TO RESOURCE conn
        THEN READ DATA msg2 FROM RESOURCE conn
        THEN RETURNS_TO SOURCE RECORD NoiseConn.
    </trl>

    Handshake pattern ``-> e, es, s, ss / <- e, ee, se`` (1-RTT, 2 frames).

    Go parity:
        ``noise.ClientHandshake``.
    """
    raise NotImplementedError("Phase C")
