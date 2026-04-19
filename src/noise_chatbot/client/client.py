"""Go-parity chatbot client.

<trl>
MODULE client CONTAINS RECORD Client AND FUNCTION connect.
RECORD Client CONTAINS RECORD conn.
</trl>
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from noise_chatbot.noise.keys import generate_keypair, hex_to_key
from noise_chatbot.noise.tcp_client import dial
from noise_chatbot.protocol.message import Message

if TYPE_CHECKING:
    from noise_chatbot.noise.conn import NoiseConn


# AGENT client SHALL AUTHENTICATE TO ENDPOINT server.
class Client:
    """An encrypted chatbot client — thin wrapper over a NoiseConn.

    <trl>DEFINE RECORD Client CONTAINS RECORD conn.</trl>
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: NoiseConn) -> None:
        self._conn = conn

    # FUNCTION chat SHALL SEND RECORD message TO ENDPOINT server.
    def chat(self, text: str) -> str:
        """Send a CHAT message, await the response, return its ``text`` payload.

        <trl>
        FUNCTION Client.chat SHALL DEFINE RECORD Message CONTAINS STRING CHAT
            AND OBJECT text THEN SEND RESULT TO ENDPOINT server
            THEN RECEIVE RESULT AS RECORD Message
            THEN MAP DATA payload AS STRING response THEN RETURNS_TO SOURCE.
        </trl>

        Message ID format: ``"msg-<unix-nano>"`` (Go parity).
        """
        msg = Message(
            type="CHAT",
            payload={"text": text},
            id=f"msg-{time.time_ns()}",
        )
        resp = self.send(msg)
        text_out: str = resp.payload.get("text", "") if isinstance(resp.payload, dict) else ""
        return text_out

    # FUNCTION send SHALL SEND RECORD message THEN RECEIVE RECORD message.
    def send(self, msg: Message) -> Message:
        """Marshal + send + receive + unmarshal a full Message.

        <trl>
        FUNCTION Client.send SHALL MAP RECORD msg AS STRING json
            THEN SEND STRING json TO RECORD conn
            THEN RECEIVE STRING json FROM RECORD conn
            THEN MAP STRING json AS RECORD Message THEN RETURNS_TO SOURCE.
        </trl>
        """
        self._conn.send(msg.to_json().encode("utf-8"))
        raw = self._conn.receive()
        return Message.from_json(raw)

    # FUNCTION close SHALL REVOKE RESOURCE conn.
    def close(self) -> None:
        """Close the underlying Noise connection.

        <trl>FUNCTION Client.close SHALL REVOKE RECORD conn.</trl>
        """
        self._conn.close()


# FUNCTION connect SHALL AUTHENTICATE TO ENDPOINT server.
def connect(addr: str, server_public_key_hex: str) -> Client:
    """Decode the server's hex pubkey, generate ephemeral client keypair, dial.

    <trl>
    FUNCTION connect SHALL MAP STRING hex AS STRING server_pub BY FUNCTION hex_to_key
        THEN DEFINE RECORD client_key BY FUNCTION generate_keypair
        THEN REQUEST RECORD NoiseConn FROM ENDPOINT addr
        SUBJECT_TO STRING server_pub BY FUNCTION dial
        THEN RETURNS_TO SOURCE RECORD Client.
    </trl>
    """
    server_pub = hex_to_key(server_public_key_hex)
    client_key = generate_keypair()
    conn = dial(addr, client_key, server_pub)
    return Client(conn=conn)
