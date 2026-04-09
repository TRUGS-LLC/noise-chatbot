package noise

import (
	"encoding/binary"
	"net"
	"testing"
)

func TestGenerateKeypair(t *testing.T) {
	kp, err := GenerateKeypair()
	if err != nil {
		t.Fatalf("GenerateKeypair: %v", err)
	}
	if len(kp.Public) != 32 {
		t.Fatalf("public key length = %d, want 32", len(kp.Public))
	}
	if len(kp.Private) != 32 {
		t.Fatalf("private key length = %d, want 32", len(kp.Private))
	}
}

func TestKeyHexRoundTrip(t *testing.T) {
	kp, err := GenerateKeypair()
	if err != nil {
		t.Fatalf("GenerateKeypair: %v", err)
	}
	hex := KeyToHex(kp.Public)
	got, err := HexToKey(hex)
	if err != nil {
		t.Fatalf("HexToKey: %v", err)
	}
	if len(got) != 32 {
		t.Fatalf("decoded key length = %d, want 32", len(got))
	}
	for i := range got {
		if got[i] != kp.Public[i] {
			t.Fatalf("key mismatch at byte %d", i)
		}
	}
}

// startTestServer starts a Noise listener on a random port and returns the
// listener, server keypair, and address. The caller must close the listener.
func startTestServer(t *testing.T) (*Listener, DHKey, string) {
	t.Helper()
	serverKey, err := GenerateKeypair()
	if err != nil {
		t.Fatalf("server keygen: %v", err)
	}
	ln, err := Listen("127.0.0.1:0", serverKey)
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	return ln, serverKey, ln.Addr().String()
}

func TestNoiseRoundTrip(t *testing.T) {
	ln, serverKey, addr := startTestServer(t)
	defer ln.Close()

	// Accept in goroutine
	errCh := make(chan error, 1)
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			errCh <- err
			return
		}
		defer conn.Close()
		msg, err := conn.Receive()
		if err != nil {
			errCh <- err
			return
		}
		if err := conn.Send(append([]byte("echo:"), msg...)); err != nil {
			errCh <- err
			return
		}
		errCh <- nil
	}()

	clientKey, err := GenerateKeypair()
	if err != nil {
		t.Fatalf("client keygen: %v", err)
	}
	conn, err := Dial(addr, clientKey, serverKey.Public)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	defer conn.Close()

	if err := conn.Send([]byte("hello")); err != nil {
		t.Fatalf("send: %v", err)
	}
	resp, err := conn.Receive()
	if err != nil {
		t.Fatalf("receive: %v", err)
	}
	if string(resp) != "echo:hello" {
		t.Fatalf("got %q, want %q", resp, "echo:hello")
	}
	if err := <-errCh; err != nil {
		t.Fatalf("server error: %v", err)
	}
}

func TestNoiseWrongKey(t *testing.T) {
	ln, _, addr := startTestServer(t)
	defer ln.Close()

	// Accept in goroutine (will fail handshake)
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		conn.Close()
	}()

	clientKey, _ := GenerateKeypair()
	wrongKey, _ := GenerateKeypair() // wrong server public key
	_, err := Dial(addr, clientKey, wrongKey.Public)
	if err == nil {
		t.Fatal("expected handshake failure with wrong server key")
	}
}

func TestNoiseEncryption(t *testing.T) {
	// Verify that bytes on the wire are not plaintext
	ln, serverKey, addr := startTestServer(t)
	defer ln.Close()

	// Set up a raw TCP tap to capture bytes
	tapLn, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("tap listen: %v", err)
	}
	defer tapLn.Close()
	tapAddr := tapLn.Addr().String()

	captured := make(chan []byte, 1)
	go func() {
		// Proxy: accept client, dial server, relay and capture
		clientConn, err := tapLn.Accept()
		if err != nil {
			return
		}
		defer clientConn.Close()
		serverConn, err := net.Dial("tcp", addr)
		if err != nil {
			return
		}
		defer serverConn.Close()

		var allBytes []byte
		buf := make([]byte, 65536)
		// Relay client -> server, capture post-handshake data
		for {
			n, err := clientConn.Read(buf)
			if n > 0 {
				allBytes = append(allBytes, buf[:n]...)
				serverConn.Write(buf[:n])
			}
			if err != nil {
				break
			}
			// After first exchange, relay server -> client
			go func() {
				for {
					n, err := serverConn.Read(buf)
					if n > 0 {
						clientConn.Write(buf[:n])
					}
					if err != nil {
						return
					}
				}
			}()
			// Give time for the message exchange
			break
		}
		// Read remaining client data
		for {
			n, err := clientConn.Read(buf)
			if n > 0 {
				allBytes = append(allBytes, buf[:n]...)
				serverConn.Write(buf[:n])
			}
			if err != nil {
				break
			}
		}
		captured <- allBytes
	}()

	// Server side accept in goroutine
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		msg, _ := conn.Receive()
		conn.Send(msg)
	}()

	clientKey, _ := GenerateKeypair()
	conn, err := Dial(tapAddr, clientKey, serverKey.Public)
	if err != nil {
		t.Fatalf("dial via tap: %v", err)
	}

	secret := "THIS_IS_A_SECRET_MESSAGE_12345"
	conn.Send([]byte(secret))
	conn.Receive()
	conn.Close()

	bytes := <-captured
	// The plaintext should NOT appear in the captured wire bytes
	for i := 0; i <= len(bytes)-len(secret); i++ {
		if string(bytes[i:i+len(secret)]) == secret {
			t.Fatal("plaintext found in captured wire bytes — encryption not working")
		}
	}
}

func TestServerMultipleClients(t *testing.T) {
	ln, serverKey, addr := startTestServer(t)
	defer ln.Close()

	// Server: accept two clients
	go func() {
		for i := 0; i < 2; i++ {
			conn, err := ln.Accept()
			if err != nil {
				return
			}
			go func() {
				defer conn.Close()
				msg, err := conn.Receive()
				if err != nil {
					return
				}
				conn.Send(append([]byte("reply:"), msg...))
			}()
		}
	}()

	results := make(chan string, 2)
	for _, label := range []string{"client1", "client2"} {
		go func(l string) {
			ck, _ := GenerateKeypair()
			c, err := Dial(addr, ck, serverKey.Public)
			if err != nil {
				results <- "error:" + err.Error()
				return
			}
			defer c.Close()
			c.Send([]byte(l))
			resp, err := c.Receive()
			if err != nil {
				results <- "error:" + err.Error()
				return
			}
			results <- string(resp)
		}(label)
	}

	for i := 0; i < 2; i++ {
		r := <-results
		if len(r) < 6 || r[:6] != "reply:" {
			t.Fatalf("unexpected response: %q", r)
		}
	}
}

func TestHelperCompiles(t *testing.T) {
	// Verify that writeFrame/readFrame work correctly via round-trip
	c1, c2 := net.Pipe()
	defer c1.Close()
	defer c2.Close()

	go func() {
		writeFrame(c1, []byte("test-frame"))
	}()

	data, err := readFrame(c2)
	if err != nil {
		t.Fatalf("readFrame: %v", err)
	}
	if string(data) != "test-frame" {
		t.Fatalf("got %q, want %q", data, "test-frame")
	}
}

func TestFrameTooLarge(t *testing.T) {
	c1, c2 := net.Pipe()
	defer c1.Close()
	defer c2.Close()

	go func() {
		// Write a frame header claiming 100000 bytes (exceeds 65536 limit)
		binary.Write(c1, binary.BigEndian, uint32(100000))
	}()

	_, err := readFrame(c2)
	if err == nil {
		t.Fatal("expected error for oversized frame")
	}
}
