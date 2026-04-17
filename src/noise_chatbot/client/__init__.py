"""Go-parity chatbot client library.

<trl>
DEFINE "client" AS MODULE.
MODULE client CONTAINS RECORD Client AND FUNCTION connect.
MODULE client DEPENDS_ON MODULE noise AND MODULE protocol.
FUNCTION connect SHALL AUTHENTICATE SUBJECT_TO STRING server_public_key.
EACH RECORD Message SHALL ENCRYPT 'with RECORD noise_ik THEN SEND TO ENDPOINT server.
</trl>
"""

from noise_chatbot.client.client import Client, connect

__all__ = ["Client", "connect"]
