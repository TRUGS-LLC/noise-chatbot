package noise

import (
	"fmt"
	"net"

	noiselib "github.com/flynn/noise"
)

// Dial connects to a server and performs a Noise_IK handshake.
// The client must know the server's static public key in advance.
func Dial(addr string, clientKey noiselib.DHKey, serverPubKey []byte) (*NoiseConn, error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("dial: %w", err)
	}

	nc, err := ClientHandshake(conn, clientKey, serverPubKey)
	if err != nil {
		conn.Close()
		return nil, err
	}
	return nc, nil
}

// ClientHandshake performs a Noise_IK handshake on an existing connection.
func ClientHandshake(conn net.Conn, clientKey noiselib.DHKey, serverPubKey []byte) (*NoiseConn, error) {
	hs, err := noiselib.NewHandshakeState(noiselib.Config{
		CipherSuite:   CipherSuite,
		Pattern:       noiselib.HandshakeIK,
		Initiator:     true,
		StaticKeypair: clientKey,
		PeerStatic:    serverPubKey,
	})
	if err != nil {
		return nil, fmt.Errorf("handshake init: %w", err)
	}

	// IK pattern: -> e, es, s, ss
	msg1, _, _, err := hs.WriteMessage(nil, nil)
	if err != nil {
		return nil, fmt.Errorf("handshake write msg1: %w", err)
	}

	// Send msg1
	if err := writeFrame(conn, msg1); err != nil {
		return nil, fmt.Errorf("handshake send msg1: %w", err)
	}

	// Read msg2
	msg2, err := readFrame(conn)
	if err != nil {
		return nil, fmt.Errorf("handshake recv msg2: %w", err)
	}

	// <- e, ee, se
	_, send, recv, err := hs.ReadMessage(nil, msg2)
	if err != nil {
		return nil, fmt.Errorf("handshake read msg2: %w", err)
	}

	return &NoiseConn{
		conn:    conn,
		encrypt: send,
		decrypt: recv,
		remote:  serverPubKey,
	}, nil
}
