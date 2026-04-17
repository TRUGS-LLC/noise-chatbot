"""Curve25519 keypair generation and hex encoding.

<trl>
MODULE noise CONTAINS FUNCTION generate_keypair AND FUNCTION key_to_hex AND FUNCTION hex_to_key.
RECORD DHKey CONTAINS STRING public AND STRING private.
</trl>
"""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


@dataclass(frozen=True, slots=True)
class DHKey:
    """A Noise static Curve25519 keypair.

    <trl>
    DEFINE RECORD DHKey CONTAINS STRING public AND STRING private.
    </trl>

    Fields are raw 32-byte values (not PEM/DER).

    Go parity:
        ``noise.DHKey`` — alias for ``flynn/noise.DHKey``.
    """

    public: bytes
    private: bytes


def generate_keypair() -> DHKey:
    """Generate a fresh Curve25519 static keypair using secure random entropy.

    <trl>
    FUNCTION generate_keypair SHALL READ DATA FROM RESOURCE rand
        THEN DEFINE A RECORD DHKey THEN RETURNS_TO SOURCE.
    </trl>

    Go parity: ``noise.GenerateKeypair`` — ``crypto/rand.Reader``.
    """
    priv = X25519PrivateKey.generate()
    private_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return DHKey(public=public_bytes, private=private_bytes)


def key_to_hex(key: bytes) -> str:
    """Encode a byte slice as a lowercase hexadecimal string.

    <trl>
    FUNCTION key_to_hex SHALL MAP DATA key AS STRING hex THEN RETURNS_TO SOURCE.
    </trl>

    Go parity: ``noise.KeyToHex`` — ``hex.EncodeToString``.
    """
    return key.hex()


def hex_to_key(s: str) -> bytes:
    """Decode a hex string to a 32-byte key.

    <trl>
    FUNCTION hex_to_key SHALL VALIDATE STRING s
        THEN REJECT IF STRING s 'is INVALID OR NOT EQUALS 32.
    FUNCTION hex_to_key SHALL MAP STRING s AS DATA key THEN RETURNS_TO SOURCE.
    </trl>

    Raises:
        ValueError: If ``s`` is not valid hex or the decoded length is not 32.

    Go parity:
        ``noise.HexToKey`` — errors ``"invalid hex key: %w"`` and
        ``"key must be 32 bytes, got %d"``.
    """
    try:
        b = bytes.fromhex(s)
    except ValueError as exc:
        raise ValueError(f"invalid hex key: {exc}") from exc
    if len(b) != 32:
        raise ValueError(f"key must be 32 bytes, got {len(b)}")
    return b
