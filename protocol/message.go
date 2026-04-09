package protocol

import "encoding/json"

// Message is the wire format for all Noise Chatbot communication.
type Message struct {
	Type    string          `json:"type"`
	Payload json.RawMessage `json:"payload"`
	ID      string          `json:"id"`
	ReplyTo string          `json:"reply_to,omitempty"`
}
