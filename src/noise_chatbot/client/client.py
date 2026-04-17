"""Go-parity chatbot client.

<trl>
MODULE client CONTAINS RECORD Client AND FUNCTION connect.
RECORD Client CONTAINS RECORD conn.
</trl>
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_chatbot.noise.conn import NoiseConn
    from noise_chatbot.protocol.message import Message


class Client:
    """An encrypted chatbot client — thin wrapper over a NoiseConn.

    <trl>DEFINE RECORD Client CONTAINS RECORD conn.</trl>

    Go parity: ``client.Client``.
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: NoiseConn) -> None:
        self._conn = conn

    def chat(self, text: str) -> str:
        """Send a CHAT message, await the response, return its ``text`` payload.

        <trl>
        FUNCTION Client.chat SHALL DEFINE RECORD Message CONTAINS STRING CHAT
            AND OBJECT text THEN SEND RESULT TO ENDPOINT server
            THEN RECEIVE RESULT AS RECORD Message
            THEN MAP DATA payload AS STRING response THEN RETURNS_TO SOURCE.
        </trl>

        Message ID format: ``"msg-<unix-nano>"`` (Go parity).

        Go parity: ``(*Client).Chat``.
        """
        raise NotImplementedError("Phase C")

    def send(self, msg: Message) -> Message:
        """Marshal + send + receive + unmarshal a full Message.

        <trl>
        FUNCTION Client.send SHALL MAP RECORD msg AS STRING json
            THEN SEND STRING json TO RECORD conn
            THEN RECEIVE STRING json FROM RECORD conn
            THEN MAP STRING json AS RECORD Message THEN RETURNS_TO SOURCE.
        </trl>

        Go parity: ``(*Client).Send``.
        """
        raise NotImplementedError("Phase C")

    def close(self) -> None:
        """Close the underlying Noise connection.

        <trl>FUNCTION Client.close SHALL REVOKE RECORD conn.</trl>
        """
        raise NotImplementedError("Phase C")


def connect(addr: str, server_public_key_hex: str) -> Client:
    """Decode the server's hex pubkey, generate ephemeral client keypair, dial.

    <trl>
    FUNCTION connect SHALL MAP STRING hex AS STRING server_pub BY FUNCTION hex_to_key
        THEN DEFINE RECORD client_key BY FUNCTION generate_keypair
        THEN REQUEST RECORD NoiseConn FROM ENDPOINT addr
        SUBJECT_TO STRING server_pub BY FUNCTION dial
        THEN RETURNS_TO SOURCE RECORD Client.
    </trl>

    Args:
        addr: ``"host:port"``.
        server_public_key_hex: Server's Curve25519 static public key, hex.

    Raises:
        ValueError: If the hex key is malformed or the wrong length.
        OSError: TCP dial failure.
        RuntimeError: Handshake failure.

    Go parity: ``client.Connect``.
    """
    raise NotImplementedError("Phase C")
