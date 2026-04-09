package protocol

import (
	"encoding/json"
	"testing"
)

func TestMessageJSON(t *testing.T) {
	original := Message{
		Type:    "CHAT",
		Payload: json.RawMessage(`{"text":"hello"}`),
		ID:      "msg-123",
		ReplyTo: "msg-000",
	}

	data, err := json.Marshal(original)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var decoded Message
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if decoded.Type != original.Type {
		t.Errorf("Type = %q, want %q", decoded.Type, original.Type)
	}
	if decoded.ID != original.ID {
		t.Errorf("ID = %q, want %q", decoded.ID, original.ID)
	}
	if decoded.ReplyTo != original.ReplyTo {
		t.Errorf("ReplyTo = %q, want %q", decoded.ReplyTo, original.ReplyTo)
	}
	if string(decoded.Payload) != string(original.Payload) {
		t.Errorf("Payload = %s, want %s", decoded.Payload, original.Payload)
	}
}

func TestMessageOmitEmptyReplyTo(t *testing.T) {
	msg := Message{
		Type:    "CHAT",
		Payload: json.RawMessage(`{}`),
		ID:      "msg-456",
	}
	data, _ := json.Marshal(msg)
	var m map[string]any
	json.Unmarshal(data, &m)
	if _, ok := m["reply_to"]; ok {
		t.Error("reply_to should be omitted when empty")
	}
}
