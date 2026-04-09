package client

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/TRUGS-LLC/noise-chatbot/noise"
	"github.com/TRUGS-LLC/noise-chatbot/protocol"
	"github.com/TRUGS-LLC/noise-chatbot/server"
)

// startServer creates a server with optional chat handler, returns addr, pub key hex, cancel.
func startServer(t *testing.T, handler func(string) string) (string, string, context.CancelFunc) {
	t.Helper()
	s := server.New("127.0.0.1:0")
	if handler != nil {
		s.OnChat(handler)
	}

	ln, err := noise.Listen("127.0.0.1:0", s.Key())
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	addr := ln.Addr().String()

	ctx, cancel := context.WithCancel(context.Background())
	go s.ServeListener(ctx, ln)
	time.Sleep(10 * time.Millisecond)

	return addr, s.PublicKey(), cancel
}

func TestClientConnect(t *testing.T) {
	addr, pubKey, cancel := startServer(t, nil)
	defer cancel()

	c, err := Connect(addr, pubKey)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer c.Close()
	// If we get here, connection succeeded
}

func TestClientChat(t *testing.T) {
	addr, pubKey, cancel := startServer(t, func(text string) string {
		return "got:" + text
	})
	defer cancel()

	c, err := Connect(addr, pubKey)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer c.Close()

	resp, err := c.Chat("test message")
	if err != nil {
		t.Fatalf("chat: %v", err)
	}
	if resp != "got:test message" {
		t.Fatalf("got %q, want %q", resp, "got:test message")
	}
}

func TestClientSendMessage(t *testing.T) {
	addr, pubKey, cancel := startServer(t, nil)
	defer cancel()

	c, err := Connect(addr, pubKey)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer c.Close()

	msg := protocol.Message{
		Type:    "PING",
		Payload: json.RawMessage(`{"v":1}`),
		ID:      "test-send-1",
	}
	resp, err := c.Send(msg)
	if err != nil {
		t.Fatalf("send: %v", err)
	}
	// Echo server returns same type and payload
	if resp.Type != "PING" {
		t.Fatalf("type = %q, want PING", resp.Type)
	}
	if resp.ReplyTo != msg.ID {
		t.Fatalf("reply_to = %q, want %q", resp.ReplyTo, msg.ID)
	}
}
