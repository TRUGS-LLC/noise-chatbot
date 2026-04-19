"""Unit tests for Curve25519 keypair helpers.

<trl>
STAGE test_keys SHALL VALIDATE FUNCTION generate_keypair AND FUNCTION key_to_hex
    AND FUNCTION hex_to_key SUBJECT_TO DATA cryptography_backend.
</trl>
"""

from __future__ import annotations

import pytest

from noise_chatbot.noise.keys import DHKey, generate_keypair, hex_to_key, key_to_hex


# AGENT SHALL VALIDATE PROCESS generate_keypair_returns_dhkey.
def test_generate_keypair_returns_dhkey() -> None:
    """``generate_keypair`` returns a ``DHKey`` with 32-byte public + private."""
    k = generate_keypair()
    assert isinstance(k, DHKey)
    assert len(k.public) == 32
    assert len(k.private) == 32


# AGENT SHALL VALIDATE PROCESS generate_keypair_is_random.
def test_generate_keypair_is_random() -> None:
    """Two successive calls yield distinct keypairs (probabilistic check)."""
    k1 = generate_keypair()
    k2 = generate_keypair()
    assert k1.private != k2.private
    assert k1.public != k2.public


# AGENT SHALL VALIDATE PROCESS key_to_hex_is_lowercase_64_chars.
def test_key_to_hex_is_lowercase_64_chars() -> None:
    """``key_to_hex`` yields a 64-char lowercase hex string for a 32-byte key."""
    k = generate_keypair()
    h = key_to_hex(k.public)
    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


# AGENT SHALL VALIDATE PROCESS hex_to_key_round_trip.
def test_hex_to_key_round_trip() -> None:
    """``hex_to_key(key_to_hex(k))`` recovers the original bytes."""
    k = generate_keypair()
    assert hex_to_key(key_to_hex(k.public)) == k.public
    assert hex_to_key(key_to_hex(k.private)) == k.private


# AGENT SHALL VALIDATE PROCESS hex_to_key_rejects_non_hex.
def test_hex_to_key_rejects_non_hex() -> None:
    """Non-hex input raises ``ValueError`` (Go parity: ``"invalid hex key"``)."""
    with pytest.raises(ValueError, match="invalid hex key"):
        hex_to_key("not-hex-at-all")


# AGENT SHALL VALIDATE PROCESS hex_to_key_rejects_wrong_length.
def test_hex_to_key_rejects_wrong_length() -> None:
    """Non-32-byte input raises ``ValueError`` (Go parity: ``"key must be 32 bytes"``)."""
    with pytest.raises(ValueError, match="key must be 32 bytes"):
        hex_to_key("aa" * 31)  # 31 bytes encoded
    with pytest.raises(ValueError, match="key must be 32 bytes"):
        hex_to_key("aa" * 33)  # 33 bytes encoded
