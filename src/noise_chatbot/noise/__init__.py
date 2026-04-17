"""Noise_IK TCP transport.

<trl>
DEFINE "noise" AS MODULE.
MODULE noise IMPLEMENTS INTERFACE encrypted_transport.
MODULE noise CONTAINS FUNCTION generate_keypair AND FUNCTION dial AND FUNCTION listen.
EACH RECORD message SHALL ENCRYPT 'with RECORD chacha20_poly1305.
EACH RECORD handshake SHALL AUTHENTICATE 'with RECORD curve25519.
</trl>
"""

from noise_chatbot.noise.conn import NoiseConn
from noise_chatbot.noise.keys import DHKey, generate_keypair, hex_to_key, key_to_hex
from noise_chatbot.noise.server import Listener, listen, server_handshake
from noise_chatbot.noise.tcp_client import client_handshake, dial

__all__ = [
    "DHKey",
    "Listener",
    "NoiseConn",
    "client_handshake",
    "dial",
    "generate_keypair",
    "hex_to_key",
    "key_to_hex",
    "listen",
    "server_handshake",
]
