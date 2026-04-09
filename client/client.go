package client

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/TRUGS-LLC/noise-chatbot/noise"
	"github.com/TRUGS-LLC/noise-chatbot/protocol"
)

// Client is an encrypted Noise Chatbot client.
type Client struct {
	conn *noise.NoiseConn
}

// Connect establishes an encrypted connection to a Noise Chatbot server.
func Connect(addr string, serverPublicKeyHex string) (*Client, error) {
	serverPub, err := noise.HexToKey(serverPublicKeyHex)
	if err != nil {
		return nil, fmt.Errorf("invalid server key: %w", err)
	}
	clientKey, err := noise.GenerateKeypair()
	if err != nil {
		return nil, fmt.Errorf("keygen: %w", err)
	}
	conn, err := noise.Dial(addr, clientKey, serverPub)
	if err != nil {
		return nil, fmt.Errorf("connect: %w", err)
	}
	return &Client{conn: conn}, nil
}

// Chat sends a text message and returns the response text.
func (c *Client) Chat(text string) (string, error) {
	msg := protocol.Message{
		Type:    "CHAT",
		Payload: mustMarshal(map[string]string{"text": text}),
		ID:      fmt.Sprintf("msg-%d", time.Now().UnixNano()),
	}
	resp, err := c.Send(msg)
	if err != nil {
		return "", err
	}
	var payload struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp.Payload, &payload)
	return payload.Text, nil
}

// Send sends a full message and returns the response.
func (c *Client) Send(msg protocol.Message) (protocol.Message, error) {
	data, err := json.Marshal(msg)
	if err != nil {
		return protocol.Message{}, fmt.Errorf("marshal: %w", err)
	}
	if err := c.conn.Send(data); err != nil {
		return protocol.Message{}, fmt.Errorf("send: %w", err)
	}
	respData, err := c.conn.Receive()
	if err != nil {
		return protocol.Message{}, fmt.Errorf("receive: %w", err)
	}
	var resp protocol.Message
	if err := json.Unmarshal(respData, &resp); err != nil {
		return protocol.Message{}, fmt.Errorf("unmarshal: %w", err)
	}
	return resp, nil
}

// Close closes the connection.
func (c *Client) Close() {
	c.conn.Close()
}

func mustMarshal(v any) json.RawMessage {
	b, _ := json.Marshal(v)
	return b
}
