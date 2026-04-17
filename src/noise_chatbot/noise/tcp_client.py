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

from noise.connection import Keypair, NoiseConnection

from noise_chatbot.noise.conn import NoiseConn
from noise_chatbot.noise.frame import read_frame, write_frame

if TYPE_CHECKING:
    from noise_chatbot.noise.keys import DHKey

# Fixed cipher suite — Curve25519 + ChaCha20-Poly1305 + BLAKE2b. Matches
# Go's ``noise.CipherSuite`` (no negotiation).
_NOISE_PROTOCOL_NAME: bytes = b"Noise_IK_25519_ChaChaPoly_BLAKE2b"


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
    host, port_str = addr.rsplit(":", 1)
    sock = socket.create_connection((host, int(port_str)))
    try:
        return client_handshake(sock, client_key, server_pub_key)
    except Exception:
        sock.close()
        raise


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

    Go parity: ``noise.ClientHandshake``.
    """
    nc = NoiseConnection.from_name(_NOISE_PROTOCOL_NAME)
    nc.set_as_initiator()
    nc.set_keypair_from_private_bytes(Keypair.STATIC, client_key.private)
    nc.set_keypair_from_public_bytes(Keypair.REMOTE_STATIC, server_pub_key)
    nc.start_handshake()

    # msg1: -> e, es, s, ss
    msg1 = nc.write_message()
    write_frame(conn, bytes(msg1))

    # msg2: <- e, ee, se
    msg2 = read_frame(conn)
    nc.read_message(msg2)

    if not nc.handshake_finished:
        raise RuntimeError("handshake did not finish after 1-RTT")

    return NoiseConn(conn=conn, noise_connection=nc, remote=server_pub_key)
