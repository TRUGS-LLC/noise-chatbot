"""Noise_IK encrypted connection.

<trl>
MODULE noise CONTAINS RECORD NoiseConn.
RECORD NoiseConn WRAPS RESOURCE socket 'with RECORD encrypt AND RECORD decrypt.
EACH RECORD NoiseConn SHALL ENCRYPT EACH DATA msg BEFORE SEND
    AND SHALL DECRYPT EACH DATA ciphertext BEFORE RECEIVE.
</trl>
"""

from __future__ import annotations

import socket
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noiseprotocol import CipherState

# <trl>DEFINE INTEGER data_frame_max_bytes AS 16777216.</trl>
DATA_FRAME_MAX_BYTES: int = 16 * 1024 * 1024


class NoiseConn:
    """An encrypted connection wrapping a raw ``socket.socket``.

    <trl>
    DEFINE RECORD NoiseConn CONTAINS RESOURCE conn AND DATA encrypt
        AND DATA decrypt AND STRING remote.
    </trl>

    Concurrency:
        ``send`` holds an internal write lock; ``receive`` holds a separate
        read lock. Concurrent read+write across two threads is permitted.
        Two threads may not concurrently send on the same connection.

    Go parity:
        ``noise/conn.go:NoiseConn`` — same two-mutex pattern (``mu`` + ``rmu``).
    """

    __slots__ = ("_conn", "_decrypt", "_encrypt", "_remote", "_rmu", "_wmu")

    def __init__(
        self,
        conn: socket.socket,
        encrypt: CipherState,
        decrypt: CipherState,
        remote: bytes,
    ) -> None:
        self._conn = conn
        self._encrypt = encrypt
        self._decrypt = decrypt
        self._remote = remote
        self._wmu = threading.Lock()
        self._rmu = threading.Lock()

    def send(self, msg: bytes) -> None:
        """Encrypt ``msg``, write 4-byte big-endian length + ciphertext to the wire.

        <trl>
        FUNCTION NoiseConn.send SHALL MAP DATA msg AS DATA ciphertext BY DATA encrypt
            THEN WRITE INTEGER length AND DATA ciphertext TO RESOURCE conn.
        FUNCTION NoiseConn.send SHALL_NOT SEND ANY DATA msg IN PARALLEL 'with SELF.
        </trl>

        Raises:
            RuntimeError: If encryption fails.
            OSError: On socket write failure.

        Go parity:
            ``(*NoiseConn).Send`` — error wrapping via ``fmt.Errorf("noise send: %w", ...)``.
        """
        raise NotImplementedError("Phase C")

    def receive(self) -> bytes:
        """Read length-prefixed ciphertext, decrypt, return plaintext.

        <trl>
        FUNCTION NoiseConn.receive SHALL READ INTEGER length FROM RESOURCE conn
            THEN REJECT IF INTEGER length EXCEEDS 16777216.
        FUNCTION NoiseConn.receive SHALL READ DATA ciphertext FROM RESOURCE conn
            THEN MAP DATA ciphertext AS DATA plaintext BY DATA decrypt.
        FUNCTION NoiseConn.receive SHALL REVOKE RESOURCE conn IF DATA decrypt FAILED.
        </trl>

        Raises:
            ValueError: If ciphertext length exceeds 16 MiB (connection closed).
            RuntimeError: On decrypt failure (connection closed).
            OSError: On socket read failure.

        Go parity:
            ``(*NoiseConn).Receive`` — 16 MiB cap, close-on-decrypt-failure.
        """
        raise NotImplementedError("Phase C")

    def close(self) -> None:
        """Close the underlying socket.

        <trl>FUNCTION NoiseConn.close SHALL REVOKE RESOURCE conn.</trl>
        """
        raise NotImplementedError("Phase C")

    def remote_identity(self) -> bytes:
        """Return the peer's static Curve25519 public key.

        <trl>FUNCTION NoiseConn.remote_identity SHALL RETURNS_TO SOURCE STRING remote.</trl>
        """
        raise NotImplementedError("Phase C")
