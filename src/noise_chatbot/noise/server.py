"""Noise_IK server-side listener + responder handshake.

<trl>
MODULE noise CONTAINS FUNCTION listen AND RECORD Listener AND FUNCTION server_handshake.
FUNCTION listen SHALL DEFINE RESOURCE Listener AT ENDPOINT addr BINDS RECORD server_key.
</trl>
"""

from __future__ import annotations

import contextlib
import socket
from dataclasses import dataclass

from noise.connection import Keypair, NoiseConnection

from noise_chatbot.noise.conn import NoiseConn
from noise_chatbot.noise.frame import read_frame, write_frame
from noise_chatbot.noise.keys import DHKey

_NOISE_PROTOCOL_NAME: bytes = b"Noise_IK_25519_ChaChaPoly_BLAKE2b"


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

        Go parity: ``(*Listener).Accept`` — error ``"accept: %w"``.
        """
        conn, _ = self.inner.accept()
        try:
            return server_handshake(conn, self.server_key)
        except Exception:
            conn.close()
            raise

    def close(self) -> None:
        """Close the listen socket.

        <trl>FUNCTION Listener.close SHALL REVOKE RESOURCE Listener.</trl>
        """
        with contextlib.suppress(OSError):
            self.inner.close()

    def addr(self) -> tuple[str, int]:
        """Return the bound ``(host, port)``.

        <trl>FUNCTION Listener.addr SHALL RETURNS_TO SOURCE ENDPOINT addr.</trl>
        """
        host, port = self.inner.getsockname()[:2]
        return (host, port)


def listen(addr: str, server_key: DHKey) -> Listener:
    """Start a TCP listener bound to the server's static key.

    <trl>
    FUNCTION listen SHALL DEFINE RESOURCE Listener AT ENDPOINT addr
        BINDS RECORD server_key THEN RETURNS_TO SOURCE.
    </trl>

    Accepts ``"host:port"`` strings where host may be empty / ``":0"`` for
    wildcard bind with ephemeral port. Go parity: ``noise.Listen``.
    """
    host_str, port_str = addr.rsplit(":", 1)
    host = host_str if host_str else "127.0.0.1"
    port = int(port_str)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(128)
    return Listener(inner=s, server_key=server_key)


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
    nc = NoiseConnection.from_name(_NOISE_PROTOCOL_NAME)
    nc.set_as_responder()
    nc.set_keypair_from_private_bytes(Keypair.STATIC, server_key.private)
    nc.start_handshake()

    # Read msg1: -> e, es, s, ss
    msg1 = read_frame(conn)
    nc.read_message(msg1)

    # Capture client's static pubkey BEFORE writing msg2, because the Noise
    # library tears down ``handshake_state`` once the handshake is finalised.
    client_pub_bytes = bytes(nc.noise_protocol.handshake_state.rs.public_bytes)

    # Write msg2: <- e, ee, se
    msg2 = nc.write_message()
    write_frame(conn, bytes(msg2))

    if not nc.handshake_finished:
        raise RuntimeError("handshake did not finish after 1-RTT")

    return NoiseConn(conn=conn, noise_connection=nc, remote=client_pub_bytes)
