package server

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/TRUGS-LLC/noise-chatbot/noise"
	"github.com/TRUGS-LLC/noise-chatbot/protocol"
)

// startTestServer creates a Server, starts it on a random port, and returns
// the server, address, cancel function. Caller must call cancel.
func startTestServer(t *testing.T) (*Server, string, context.CancelFunc) {
	t.Helper()
	s := New("127.0.0.1:0")

	ln, err := noise.Listen("127.0.0.1:0", s.Key())
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	addr := ln.Addr().String()

	ctx, cancel := context.WithCancel(context.Background())
	go s.ServeListener(ctx, ln)

	// Give the server a moment to start accepting
	time.Sleep(10 * time.Millisecond)
	return s, addr, cancel
}

func connectClient(t *testing.T, addr string, serverPub []byte) *noise.NoiseConn {
	t.Helper()
	ck, err := noise.GenerateKeypair()
	if err != nil {
		t.Fatalf("client keygen: %v", err)
	}
	conn, err := noise.Dial(addr, ck, serverPub)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	return conn
}

func sendChat(t *testing.T, conn *noise.NoiseConn, text string) string {
	t.Helper()
	msg := protocol.Message{
		Type:    "CHAT",
		Payload: json.RawMessage(`{"text":"` + text + `"}`),
		ID:      "test-msg-1",
	}
	data, _ := json.Marshal(msg)
	if err := conn.Send(data); err != nil {
		t.Fatalf("send: %v", err)
	}
	respData, err := conn.Receive()
	if err != nil {
		t.Fatalf("receive: %v", err)
	}
	var resp protocol.Message
	json.Unmarshal(respData, &resp)
	var payload struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp.Payload, &payload)
	return payload.Text
}

func TestServerOnChat(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	handlerCalled := false
	s.OnChat(func(text string) string {
		handlerCalled = true
		return "response:" + text
	})

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	got := sendChat(t, conn, "hello")
	if !handlerCalled {
		t.Fatal("chat handler was not called")
	}
	if got != "response:hello" {
		t.Fatalf("got %q, want %q", got, "response:hello")
	}
}

func TestServerEcho(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()
	// No handler set — should echo

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	msg := protocol.Message{
		Type:    "PING",
		Payload: json.RawMessage(`{"value":42}`),
		ID:      "echo-1",
	}
	data, _ := json.Marshal(msg)
	conn.Send(data)

	respData, err := conn.Receive()
	if err != nil {
		t.Fatalf("receive: %v", err)
	}
	var resp protocol.Message
	json.Unmarshal(respData, &resp)

	if resp.Type != "PING" {
		t.Fatalf("type = %q, want PING", resp.Type)
	}
	if resp.ReplyTo != "echo-1" {
		t.Fatalf("reply_to = %q, want echo-1", resp.ReplyTo)
	}
	if string(resp.Payload) != `{"value":42}` {
		t.Fatalf("payload = %s, want {\"value\":42}", resp.Payload)
	}
}

func TestServerGracefulShutdown(t *testing.T) {
	_, _, cancel := startTestServer(t)

	// Cancel the context to trigger shutdown
	cancel()

	// Give the server time to shut down
	time.Sleep(50 * time.Millisecond)

	// If we get here without hanging, shutdown worked
}

func TestServerMultipleClients(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.OnChat(func(text string) string {
		return "reply:" + text
	})

	results := make(chan string, 2)
	for _, label := range []string{"A", "B"} {
		go func(l string) {
			conn := connectClient(t, addr, s.Key().Public)
			defer conn.Close()
			got := sendChat(t, conn, l)
			results <- got
		}(label)
	}

	seen := map[string]bool{}
	for i := 0; i < 2; i++ {
		r := <-results
		seen[r] = true
	}
	if !seen["reply:A"] || !seen["reply:B"] {
		t.Fatalf("expected both replies, got %v", seen)
	}
}

func TestGetTRUGContext(t *testing.T) {
	s := New("127.0.0.1:0")
	// No TRUG loaded
	if got := s.GetTRUGContext(); got != "" {
		t.Fatalf("expected empty context, got %q", got)
	}

	// Manually set TRUG data
	s.trugData = map[string]any{
		"nodes": []any{
			map[string]any{
				"properties": map[string]any{
					"name":        "TestNode",
					"description": "A test node",
				},
			},
		},
	}
	ctx := s.GetTRUGContext()
	if ctx == "" {
		t.Fatal("expected non-empty TRUG context")
	}
	if !contains(ctx, "TestNode") || !contains(ctx, "A test node") {
		t.Fatalf("TRUG context missing expected content: %q", ctx)
	}
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && searchString(s, sub)
}

func searchString(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
