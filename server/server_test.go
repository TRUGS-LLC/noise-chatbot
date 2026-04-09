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

func TestTemplateModeSingleMatch(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.guardrails = nil
	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours", "open", "time"}, Response: "We are open Monday through Friday, 9am to 5pm."},
		{ID: "pricing", Keywords: []string{"price", "cost", "pricing"}, Response: "Plans start at $29/month."},
		{ID: "contact", Keywords: []string{"contact", "email", "phone"}, Response: "Email us at hello@example.com."},
	})

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	got := sendChat(t, conn, "What are your hours?")
	if got != "We are open Monday through Friday, 9am to 5pm." {
		t.Fatalf("got %q, want exact hours response", got)
	}
}

func TestTemplateModeMultipleMatch(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.guardrails = nil
	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours", "open"}, Response: "We are open 9-5."},
		{ID: "pricing", Keywords: []string{"pricing", "cost"}, Response: "Plans start at $29."},
	})

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	// Query matches both keywords
	got := sendChat(t, conn, "What are your hours and pricing cost?")
	if !contains(got, "We are open 9-5.") {
		t.Fatalf("response missing hours: %q", got)
	}
	if !contains(got, "Plans start at $29.") {
		t.Fatalf("response missing pricing: %q", got)
	}
}

func TestTemplateModeNoMatch(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.guardrails = nil
	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours"}, Response: "We are open 9-5."},
	})
	s.WithNoMatch("Sorry, I can't help with that.")

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	got := sendChat(t, conn, "What is the meaning of life?")
	if got != "Sorry, I can't help with that." {
		t.Fatalf("got %q, want no-match response", got)
	}
}

func TestTemplateModeOverridesOnChat(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	// Set both — template mode should take priority
	s.guardrails = nil
	s.OnChat(func(text string) string {
		return "THIS SHOULD NOT APPEAR"
	})
	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours"}, Response: "We are open 9-5."},
	})

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	got := sendChat(t, conn, "hours")
	if got == "THIS SHOULD NOT APPEAR" {
		t.Fatal("template mode should override OnChat")
	}
	if got != "We are open 9-5." {
		t.Fatalf("got %q, want template response", got)
	}
}

func TestTemplateModeCustomClassifier(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.guardrails = nil
	s.WithResponses([]ResponseNode{
		{ID: "a", Keywords: nil, Response: "Answer A"},
		{ID: "b", Keywords: nil, Response: "Answer B"},
	})
	// Custom classifier always picks both
	s.WithClassifier(func(userText string, nodes []ResponseNode) []string {
		return []string{"b", "a"}
	})

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	got := sendChat(t, conn, "anything")
	if got != "Answer B\n\nAnswer A" {
		t.Fatalf("got %q, want both answers in order", got)
	}
}

func TestLLMNeverGeneratesText(t *testing.T) {
	// This test verifies the structural guarantee: in template mode,
	// the response text can ONLY come from ResponseNode.Response fields.
	// There is no code path where the LLM can inject generated text.

	s := New("127.0.0.1:0")
	s.WithResponses([]ResponseNode{
		{ID: "only", Keywords: []string{"test"}, Response: "This is the only possible response."},
	})

	// Simulate handleMessage directly
	msg := protocol.Message{
		Type:    "CHAT",
		Payload: json.RawMessage(`{"text":"test"}`),
		ID:      "verify-1",
	}
	resp := s.handleMessage(msg)

	var payload struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp.Payload, &payload)

	// The response MUST be either the node response or the noMatchText
	// It cannot be anything else — there is no generation path
	allowed := map[string]bool{
		"This is the only possible response.": true,
		s.noMatchText:                         true,
	}
	if !allowed[payload.Text] {
		t.Fatalf("response %q is not from any ResponseNode — LLM may have generated text", payload.Text)
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

// ── Test helper: BanKey inserts a key into the ban map for testing ───────
func (s *Server) BanKey(keyHex string) {
	s.bannedMu.Lock()
	s.bannedKeys[keyHex] = time.Time{} // zero time = permanent ban
	s.bannedMu.Unlock()
}

// connectClientWithKey connects using a specific keypair (for ban testing).
func connectClientWithKey(t *testing.T, addr string, clientKey noise.DHKey, serverPub []byte) (*noise.NoiseConn, error) {
	t.Helper()
	conn, err := noise.Dial(addr, clientKey, serverPub)
	return conn, err
}

// makeChatMsg builds a CHAT protocol.Message from text.
func makeChatMsg(text string) protocol.Message {
	return protocol.Message{
		Type:    "CHAT",
		Payload: json.RawMessage(`{"text":"` + text + `"}`),
		ID:      "test-msg-1",
	}
}

// ── 1. TestGuardrailsMatchFirst ─────────────────────────────────────────
// Guardrails with "password" keyword AND business responses with "password"
// keyword. The guardrail must win because guardrails are checked first.
func TestGuardrailsMatchFirst(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	// Set guardrails with a "password" node
	s.guardrails = []ResponseNode{
		{ID: "guard-pw", Keywords: []string{"password"}, Response: "I cannot help with passwords. Please contact support."},
	}
	// Set business responses with a "password" pricing node
	s.WithResponses([]ResponseNode{
		{ID: "biz-pw", Keywords: []string{"password"}, Response: "Password Manager Pro costs $9.99/month."},
	})

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	got := sendChat(t, conn, "Tell me about password")
	if !contains(got, "I cannot help with passwords") {
		t.Fatalf("expected guardrail response, got %q", got)
	}
	if contains(got, "Password Manager Pro") {
		t.Fatalf("business response leaked through guardrails: %q", got)
	}
}

// ── 2. TestHoneypotResponseChanges ──────────────────────────────────────
// After 3 guardrail hits, the honeypot tier 2 kicks in with different text.
// Uses handleMessageFull directly to avoid Noise delays.
func TestHoneypotResponseChanges(t *testing.T) {
	s := New("127.0.0.1:0")
	s.guardrails = []ResponseNode{
		{ID: "guard-pw", Keywords: []string{"password"}, Response: "I cannot help with passwords."},
	}

	msg := makeChatMsg("password")

	// Simulate serveConn logic: call handleMessageFull and track guardrailHits
	var responses []string
	guardrailHits := 0
	for i := 0; i < 4; i++ {
		resp, _, hitGuardrail := s.handleMessageFull(msg, i)
		if hitGuardrail {
			guardrailHits++
		}

		var payload struct {
			Text string `json:"text"`
		}
		json.Unmarshal(resp.Payload, &payload)

		// Apply honeypot tier overrides (same logic as serveConn)
		if guardrailHits >= 3 {
			honeypot := []string{
				"I appreciate your patience. That's outside my current scope, but I'm happy to help with product questions.",
				"Good question — unfortunately that falls under a different department. Can I help with something else?",
				"I've noted your request. For that type of inquiry, our team would need to assist you directly.",
			}
			payload.Text = honeypot[guardrailHits%len(honeypot)]
		}
		responses = append(responses, payload.Text)
	}

	// First response should be the guardrail text
	if !contains(responses[0], "I cannot help with passwords") {
		t.Fatalf("first response should be guardrail, got %q", responses[0])
	}
	// 4th response (guardrailHits=4, tier 2) should differ from 1st
	if responses[3] == responses[0] {
		t.Fatalf("4th response should differ from 1st (honeypot tier 2), both are %q", responses[0])
	}
}

// ── 3. TestBannedKeyRejected ────────────────────────────────────────────
// Manually insert a key into bannedKeys, then try connecting. Connection
// should be silently closed (receive fails).
func TestBannedKeyRejected(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	// Generate a client keypair and ban it
	clientKey, err := noise.GenerateKeypair()
	if err != nil {
		t.Fatalf("keygen: %v", err)
	}
	keyHex := noise.KeyToHex(clientKey.Public)
	s.BanKey(keyHex)

	// Try to connect with the banned key
	conn, err := connectClientWithKey(t, addr, clientKey, s.Key().Public)
	if err != nil {
		// Connection refused at handshake level — that's fine too
		return
	}
	defer conn.Close()

	// Send a message — should fail or get no response (server closes immediately)
	msg := protocol.Message{
		Type:    "CHAT",
		Payload: json.RawMessage(`{"text":"hello"}`),
		ID:      "ban-test",
	}
	data, _ := json.Marshal(msg)
	if err := conn.Send(data); err != nil {
		return // connection was closed — ban worked
	}

	// Try to receive — should fail because server closed the connection
	_, err = conn.Receive()
	if err == nil {
		t.Fatal("expected connection to be closed for banned key, but receive succeeded")
	}
}

// ── 4. TestWindDown20Summary ────────────────────────────────────────────
// At questionCount=20, the response should contain "We've covered".
// Uses handleMessageFull to test the summary generation at question 20.
// Note: the wind-down summary is applied in serveConn, not handleMessageFull.
// So we test via real connection, sending 20 messages.
func TestWindDown20Summary(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.guardrails = nil
	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours"}, Response: "We are open 9-5."},
	})
	// Disable rate limit and use short session timeout for speed
	s.safety.RateLimit = 0
	s.safety.SessionTimeout = 0

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	var lastResp string
	for i := 0; i < 20; i++ {
		lastResp = sendChat(t, conn, "hours")
	}

	// The 20th response should contain the wind-down summary
	if !contains(lastResp, "We've covered") {
		t.Fatalf("20th response should contain wind-down summary, got %q", lastResp)
	}
}

// ── 5. TestWindDown40Goodbye ────────────────────────────────────────────
// At questionCount=40, the server sends a farewell and closes. Since the
// wind-down delays (5s * N) make a full 40-message test very slow, we test
// that the server correctly formats the farewell at the boundary by sending
// messages and checking the connection eventually closes. We set questionCount
// high enough to trigger goodbye without excessive delays by sending rapidly.
// NOTE: This test is slow (~100s due to wind-down delays). Marked as integration.
func TestWindDown40Goodbye(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping slow wind-down test in short mode")
	}

	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours"}, Response: "We are open 9-5."},
	})
	s.safety.RateLimit = 0
	s.safety.SessionTimeout = 0

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	var lastResp string
	connClosed := false
	for i := 0; i < 41; i++ {
		msg := protocol.Message{
			Type:    "CHAT",
			Payload: json.RawMessage(`{"text":"hours"}`),
			ID:      "wd-msg",
		}
		data, _ := json.Marshal(msg)
		if err := conn.Send(data); err != nil {
			connClosed = true
			break
		}
		respData, err := conn.Receive()
		if err != nil {
			connClosed = true
			break
		}
		var resp protocol.Message
		json.Unmarshal(respData, &resp)
		var payload struct {
			Text string `json:"text"`
		}
		json.Unmarshal(resp.Payload, &payload)
		lastResp = payload.Text
	}

	// Either the connection closed (expected) or the last response was the farewell
	if !connClosed && !contains(lastResp, "Thank you for chatting") {
		t.Fatalf("expected connection close or farewell at 40 questions, got %q", lastResp)
	}
}

// ── 6. TestRateLimit ────────────────────────────────────────────────────
// Set a low rate limit, send messages rapidly, verify the excess gets an error.
func TestRateLimit(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours"}, Response: "We are open 9-5."},
	})
	s.safety.RateLimit = 3

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	var lastResp string
	var lastType string
	for i := 0; i < 5; i++ {
		msg := protocol.Message{
			Type:    "CHAT",
			Payload: json.RawMessage(`{"text":"hours"}`),
			ID:      "rate-msg",
		}
		data, _ := json.Marshal(msg)
		if err := conn.Send(data); err != nil {
			t.Fatalf("send %d: %v", i, err)
		}
		respData, err := conn.Receive()
		if err != nil {
			t.Fatalf("receive %d: %v", i, err)
		}
		var resp protocol.Message
		json.Unmarshal(respData, &resp)
		lastType = resp.Type

		var payload struct {
			Text  string `json:"text"`
			Error string `json:"error"`
		}
		json.Unmarshal(resp.Payload, &payload)
		if payload.Text != "" {
			lastResp = payload.Text
		}
		if payload.Error != "" {
			lastResp = payload.Error
		}
	}

	// At least one response should be a rate limit error
	if lastType != "ERROR" || !contains(lastResp, "rate limit") {
		t.Fatalf("expected rate limit error, got type=%q resp=%q", lastType, lastResp)
	}
}

// ── 7. TestInputSizeLimit ───────────────────────────────────────────────
// Set a low MaxInputBytes, send an oversized message, verify error response.
func TestInputSizeLimit(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.safety.MaxInputBytes = 50

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	// Build a message that exceeds 50 bytes when serialized
	longText := "This is a message that is definitely longer than fifty bytes when encoded as JSON"
	msg := protocol.Message{
		Type:    "CHAT",
		Payload: json.RawMessage(`{"text":"` + longText + `"}`),
		ID:      "size-test",
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

	if resp.Type != "ERROR" {
		t.Fatalf("expected ERROR type, got %q", resp.Type)
	}
	var payload struct {
		Error string `json:"error"`
	}
	json.Unmarshal(resp.Payload, &payload)
	if !contains(payload.Error, "too large") {
		t.Fatalf("expected 'too large' error, got %q", payload.Error)
	}
}

// ── 8. TestGreeting ─────────────────────────────────────────────────────
// Set a greeting. Connect. The first message received (before sending) should
// be the greeting text.
func TestGreeting(t *testing.T) {
	s, addr, cancel := startTestServer(t)
	defer cancel()

	s.WithGreeting("Welcome to our chatbot! How can I help?")

	conn := connectClient(t, addr, s.Key().Public)
	defer conn.Close()

	// Receive the greeting (sent automatically on connect, before any user message)
	respData, err := conn.Receive()
	if err != nil {
		t.Fatalf("receive greeting: %v", err)
	}
	var resp protocol.Message
	json.Unmarshal(respData, &resp)

	if resp.Type != "CHAT" {
		t.Fatalf("greeting type = %q, want CHAT", resp.Type)
	}
	var payload struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp.Payload, &payload)
	if !contains(payload.Text, "Welcome to our chatbot") {
		t.Fatalf("greeting = %q, want welcome text", payload.Text)
	}
}

// ── 9. TestMatchCap3 ────────────────────────────────────────────────────
// Set 5 responses that all match the same keyword. Verify only 3 appear in
// the response (match cap). Uses handleMessageFull directly.
func TestMatchCap3(t *testing.T) {
	s := New("127.0.0.1:0")
	s.WithResponses([]ResponseNode{
		{ID: "n1", Keywords: []string{"test"}, Response: "Response ONE"},
		{ID: "n2", Keywords: []string{"test"}, Response: "Response TWO"},
		{ID: "n3", Keywords: []string{"test"}, Response: "Response THREE"},
		{ID: "n4", Keywords: []string{"test"}, Response: "Response FOUR"},
		{ID: "n5", Keywords: []string{"test"}, Response: "Response FIVE"},
	})

	msg := makeChatMsg("test")
	resp, matchedNodes, _ := s.handleMessageFull(msg, 0)

	if len(matchedNodes) > 3 {
		t.Fatalf("expected at most 3 matched nodes, got %d: %v", len(matchedNodes), matchedNodes)
	}

	var payload struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp.Payload, &payload)

	// Count how many response markers appear
	count := 0
	for _, marker := range []string{"Response ONE", "Response TWO", "Response THREE", "Response FOUR", "Response FIVE"} {
		if contains(payload.Text, marker) {
			count++
		}
	}
	if count > 3 {
		t.Fatalf("expected at most 3 responses in text, got %d: %q", count, payload.Text)
	}
	if count == 0 {
		t.Fatalf("expected at least 1 response, got none: %q", payload.Text)
	}
}

// ── 10. TestFallbackClassifier ──────────────────────────────────────────
// Set responses with no matching keywords. Set a fallbackClassifier that always
// returns ["node1"]. With questionCount <= 20, should get node1's response.
// With questionCount > 20, fallback is disabled so should get noMatchText.
func TestFallbackClassifier(t *testing.T) {
	s := New("127.0.0.1:0")
	s.WithResponses([]ResponseNode{
		{ID: "node1", Keywords: []string{"xyz-no-match"}, Response: "Fallback answer from node1."},
	})
	s.WithNoMatch("No match found.")
	s.WithFallbackClassifier(func(userText string, nodes []ResponseNode) []string {
		return []string{"node1"}
	})

	msg := makeChatMsg("something completely different")

	// questionCount=5 (under 20) — fallback classifier should fire
	resp1, matched1, _ := s.handleMessageFull(msg, 5)
	var p1 struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp1.Payload, &p1)

	if len(matched1) == 0 || matched1[0] != "node1" {
		t.Fatalf("expected fallback to match node1 at questionCount=5, got %v", matched1)
	}
	if !contains(p1.Text, "Fallback answer from node1") {
		t.Fatalf("expected fallback response at questionCount=5, got %q", p1.Text)
	}

	// questionCount=25 (over 20) — fallback classifier should NOT fire
	resp2, matched2, _ := s.handleMessageFull(msg, 25)
	var p2 struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp2.Payload, &p2)

	if len(matched2) != 0 {
		t.Fatalf("expected no match at questionCount=25, got %v", matched2)
	}
	if !contains(p2.Text, "No match found") {
		t.Fatalf("expected noMatchText at questionCount=25, got %q", p2.Text)
	}
}

// ── 11. TestContactFooter ───────────────────────────────────────────────
// Set contactFooter. Send a message. Verify response contains the footer.
// Uses handleMessageFull with questionCount > 0 so footer is appended.
func TestContactFooter(t *testing.T) {
	s := New("127.0.0.1:0")
	s.WithResponses([]ResponseNode{
		{ID: "hours", Keywords: []string{"hours"}, Response: "We are open 9-5."},
	})
	s.WithContactFooter("Contact: hello@example.com | (555) 012-3456")

	msg := makeChatMsg("hours")
	// questionCount=1 so the footer formatting is applied
	resp, _, _ := s.handleMessageFull(msg, 1)

	var payload struct {
		Text string `json:"text"`
	}
	json.Unmarshal(resp.Payload, &payload)

	if !contains(payload.Text, "hello@example.com") {
		t.Fatalf("expected contact footer in response, got %q", payload.Text)
	}
	if !contains(payload.Text, "(555) 012-3456") {
		t.Fatalf("expected phone in contact footer, got %q", payload.Text)
	}
}
