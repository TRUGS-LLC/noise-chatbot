package noise

import (
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"sync"

	noiselib "github.com/flynn/noise"
)

// NoiseConn wraps a net.Conn with Noise encryption.
type NoiseConn struct {
	conn    net.Conn
	encrypt *noiselib.CipherState
	decrypt *noiselib.CipherState
	remote  []byte // peer's static public key
	mu      sync.Mutex
	rmu     sync.Mutex
}

// Send encrypts and sends a message. Thread-safe.
func (nc *NoiseConn) Send(msg []byte) error {
	nc.mu.Lock()
	defer nc.mu.Unlock()

	ciphertext, err := nc.encrypt.Encrypt(nil, nil, msg)
	if err != nil {
		return fmt.Errorf("noise encrypt: %w", err)
	}

	// Length-prefix framing: 4 bytes big-endian length + ciphertext
	length := uint32(len(ciphertext))
	if err := binary.Write(nc.conn, binary.BigEndian, length); err != nil {
		return fmt.Errorf("noise send length: %w", err)
	}
	if _, err := nc.conn.Write(ciphertext); err != nil {
		return fmt.Errorf("noise send: %w", err)
	}
	return nil
}

// Receive reads and decrypts a message. Thread-safe.
func (nc *NoiseConn) Receive() ([]byte, error) {
	nc.rmu.Lock()
	defer nc.rmu.Unlock()

	var length uint32
	if err := binary.Read(nc.conn, binary.BigEndian, &length); err != nil {
		return nil, fmt.Errorf("noise recv length: %w", err)
	}

	// Sanity check: max 16MB message. Close connection on violation to
	// prevent resource exhaustion from malformed or malicious peers.
	if length > 16*1024*1024 {
		nc.conn.Close()
		return nil, fmt.Errorf("noise recv: message too large (%d bytes)", length)
	}

	ciphertext := make([]byte, length)
	if _, err := io.ReadFull(nc.conn, ciphertext); err != nil {
		return nil, fmt.Errorf("noise recv: %w", err)
	}

	plaintext, err := nc.decrypt.Decrypt(nil, nil, ciphertext)
	if err != nil {
		// Decrypt failure means the session is compromised or the peer sent
		// garbage. Close the connection to prevent further use.
		nc.conn.Close()
		return nil, fmt.Errorf("noise decrypt: %w", err)
	}

	return plaintext, nil
}

// Close closes the underlying connection.
func (nc *NoiseConn) Close() error {
	return nc.conn.Close()
}

// RemoteIdentity returns the peer's static public key.
func (nc *NoiseConn) RemoteIdentity() []byte {
	return nc.remote
}
