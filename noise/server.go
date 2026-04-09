package noise

import (
	"fmt"
	"net"

	noiselib "github.com/flynn/noise"
)

// Listener wraps a net.Listener and performs Noise_IK handshakes on incoming connections.
type Listener struct {
	inner     net.Listener
	serverKey noiselib.DHKey
}

// Listen creates a Noise listener on the given address.
func Listen(addr string, serverKey noiselib.DHKey) (*Listener, error) {
	l, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("listen: %w", err)
	}
	return &Listener{inner: l, serverKey: serverKey}, nil
}

// Accept waits for an incoming connection and performs a Noise_IK handshake.
func (l *Listener) Accept() (*NoiseConn, error) {
	conn, err := l.inner.Accept()
	if err != nil {
		return nil, fmt.Errorf("accept: %w", err)
	}

	nc, err := ServerHandshake(conn, l.serverKey)
	if err != nil {
		conn.Close()
		return nil, err
	}
	return nc, nil
}

// Close closes the listener.
func (l *Listener) Close() error {
	return l.inner.Close()
}

// Addr returns the listener's address.
func (l *Listener) Addr() net.Addr {
	return l.inner.Addr()
}

// ServerHandshake performs a Noise_IK handshake on an existing connection (responder side).
func ServerHandshake(conn net.Conn, serverKey noiselib.DHKey) (*NoiseConn, error) {
	hs, err := noiselib.NewHandshakeState(noiselib.Config{
		CipherSuite:   CipherSuite,
		Pattern:       noiselib.HandshakeIK,
		Initiator:     false,
		StaticKeypair: serverKey,
	})
	if err != nil {
		return nil, fmt.Errorf("handshake init: %w", err)
	}

	// Read msg1: -> e, es, s, ss
	msg1, err := readFrame(conn)
	if err != nil {
		return nil, fmt.Errorf("handshake recv msg1: %w", err)
	}

	_, _, _, err = hs.ReadMessage(nil, msg1)
	if err != nil {
		return nil, fmt.Errorf("handshake read msg1: %w", err)
	}

	// Write msg2: <- e, ee, se
	msg2, recv, send, err := hs.WriteMessage(nil, nil)
	if err != nil {
		return nil, fmt.Errorf("handshake write msg2: %w", err)
	}

	if err := writeFrame(conn, msg2); err != nil {
		return nil, fmt.Errorf("handshake send msg2: %w", err)
	}

	// Extract client's static public key from handshake
	clientPub := hs.PeerStatic()

	return &NoiseConn{
		conn:    conn,
		encrypt: send,
		decrypt: recv,
		remote:  clientPub,
	}, nil
}
