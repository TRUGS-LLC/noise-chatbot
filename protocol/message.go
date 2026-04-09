package protocol

// <trl>
// DEFINE "protocol" AS MODULE.
// MODULE protocol CONTAINS RECORD Message.
// RECORD Message CONTAINS STRING type AND DATA payload AND STRING id AND OPTIONAL STRING reply_to.
// </trl>

import "encoding/json"

// Message is the wire format for all Noise Chatbot communication.
type Message struct {
	Type    string          `json:"type"`
	Payload json.RawMessage `json:"payload"`
	ID      string          `json:"id"`
	ReplyTo string          `json:"reply_to,omitempty"`
}
