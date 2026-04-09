package server

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/TRUGS-LLC/noise-chatbot/noise"
	"github.com/TRUGS-LLC/noise-chatbot/protocol"
	"github.com/google/uuid"
)

// ResponseNode is a pre-authored response in the TRUG. The LLM picks one.
// The LLM never composes text — every word the user sees was written by a human.
type ResponseNode struct {
	ID       string `json:"id"`
	Keywords []string `json:"keywords"` // matching keywords for classification
	Response string `json:"response"` // the exact text returned to the user
}

// Classifier picks one or more ResponseNode IDs given user text and available nodes.
// The LLM implements this — it reads the question, picks the best matching node IDs.
// It NEVER generates the response text. It only returns node IDs.
// Multiple IDs = multiple response nodes concatenated in order.
type Classifier func(userText string, nodes []ResponseNode) []string

// ChatHandler is the simple text chat callback (legacy — allows free text).
// DEPRECATED: Use WithResponses + WithClassifier for safe template-only responses.
type ChatHandler func(text string) string

// MessageHandler is the full message callback.
type MessageHandler func(msg protocol.Message) protocol.Message

// Server is an encrypted chatbot server using Noise_IK.
//
// Two modes:
//   - Template mode (safe): LLM classifies user input → picks a ResponseNode → returns verbatim text
//   - Handler mode (legacy): OnChat callback returns arbitrary text — LLM can compose (unsafe)
//
// Template mode is the default when WithResponses is used. The LLM never touches the output.
// SafetyConfig configures defensive options for the chatbot.
type SafetyConfig struct {
	MaxInputTokens   int           // max tokens per message (0 = unlimited, default 200)
	MaxInputBytes    int           // max bytes per message (0 = unlimited, default 2000)
	RateLimit        int           // max messages per minute per connection (0 = unlimited, default 30)
	SessionTimeout   time.Duration // disconnect after idle time (0 = no timeout, default 30m)
	Greeting         string        // first message sent on connect (empty = no greeting)
	ConfidenceMin    int           // minimum keyword matches to respond (0 = any match, default 1)
}

// ConnectionStats tracks per-connection analytics.
type ConnectionStats struct {
	MessagesReceived int
	NodeHits         map[string]int // node ID → hit count
	NoMatchCount     int
	ConnectedAt      time.Time
	LastMessageAt    time.Time
}

type Server struct {
	addr         string
	key          noise.DHKey
	chatHandler  ChatHandler
	msgHandler   MessageHandler
	trugData     map[string]any
	llmConfig    *LLMConfig
	upstreamAddr string
	upstreamKey  string

	// Template-only mode — LLM classifies, never composes
	responses          []ResponseNode
	guardrails         []ResponseNode // built-in guardrails (always checked first)
	classifier         Classifier
	fallbackClassifier Classifier // LLM-based, called when keywords don't match (disabled after 20 Q)
	noMatchText        string     // returned when classifier finds no match

	// Safety
	safety       SafetyConfig
	bannedKeys   map[string]time.Time // Noise public key → ban time
	bannedMu     sync.RWMutex

	// Response formatting
	contactFooter string // appended to every response (email, phone, URL)

	// Analytics callback — called for every message
	onAnalytics  func(stats ConnectionStats, question string, matchedNodes []string)
}

// LLMConfig configures an LLM provider for classification.
type LLMConfig struct {
	Provider  string // "anthropic" or "openai"
	Model     string
	APIKeyEnv string
}

// New creates a new Noise Chatbot server with safe defaults.
func New(addr string) *Server {
	key, _ := noise.GenerateKeypair()
	return &Server{
		addr:        addr,
		key:         key,
		noMatchText: "I don't have information about that. Please contact us directly.",
		bannedKeys:  make(map[string]time.Time),
		safety: SafetyConfig{
			MaxInputTokens: 200,
			MaxInputBytes:  2000,
			RateLimit:      30,
			SessionTimeout: 30 * time.Minute,
			ConfidenceMin:  1,
		},
	}
}

// WithSafety configures safety options (input limits, rate limiting, timeouts).
func (s *Server) WithSafety(cfg SafetyConfig) *Server {
	s.safety = cfg
	return s
}

// WithGreeting sets the first message sent when a user connects.
func (s *Server) WithGreeting(text string) *Server {
	s.safety.Greeting = text
	return s
}

// WithGuardrails loads the built-in guardrails TRUG. These response nodes
// are checked BEFORE the business responses, handling common boundary
// questions (identity, passwords, prompt injection, etc.) with pre-authored
// friendly answers.
func (s *Server) WithGuardrails(path string) *Server {
	data, err := os.ReadFile(path)
	if err != nil {
		log.Printf("warning: could not load guardrails %s: %v", path, err)
		return s
	}
	var trug struct {
		Nodes []struct {
			ID         string         `json:"id"`
			Properties map[string]any `json:"properties"`
		} `json:"nodes"`
	}
	if err := json.Unmarshal(data, &trug); err != nil {
		return s
	}
	for _, n := range trug.Nodes {
		response, _ := n.Properties["response"].(string)
		if response == "" {
			continue
		}
		var keywords []string
		if kw, ok := n.Properties["keywords"].([]any); ok {
			for _, k := range kw {
				if str, ok := k.(string); ok {
					keywords = append(keywords, str)
				}
			}
		}
		s.guardrails = append(s.guardrails, ResponseNode{
			ID:       n.ID,
			Keywords: keywords,
			Response: response,
		})
	}
	log.Printf("Loaded %d guardrail nodes from %s", len(s.guardrails), path)
	return s
}

// OnAnalytics sets a callback for every message — useful for logging
// which questions are asked and which nodes match.
func (s *Server) OnAnalytics(fn func(stats ConnectionStats, question string, matchedNodes []string)) *Server {
	s.onAnalytics = fn
	return s
}

// WithResponses loads pre-authored response nodes. The LLM picks from these —
// it never generates text. Every word the user sees was written by a human.
//
// This is the safe mode. Use this instead of OnChat.
func (s *Server) WithResponses(nodes []ResponseNode) *Server {
	s.responses = nodes
	return s
}

// WithResponsesFromTRUG loads response nodes from a .trug.json file.
// Each node with a "response" property becomes a ResponseNode.
// Keywords are extracted from the "keywords" property (array of strings)
// or generated from the node name and description.
func (s *Server) WithResponsesFromTRUG(path string) *Server {
	data, err := os.ReadFile(path)
	if err != nil {
		log.Printf("warning: could not load TRUG %s: %v", path, err)
		return s
	}
	var trug struct {
		Nodes []struct {
			ID         string         `json:"id"`
			Properties map[string]any `json:"properties"`
		} `json:"nodes"`
	}
	if err := json.Unmarshal(data, &trug); err != nil {
		log.Printf("warning: could not parse TRUG %s: %v", path, err)
		return s
	}

	var nodes []ResponseNode
	for _, n := range trug.Nodes {
		response, _ := n.Properties["response"].(string)
		if response == "" {
			// Fall back to description
			response, _ = n.Properties["description"].(string)
		}
		if response == "" {
			continue // skip nodes without response text
		}

		var keywords []string
		if kw, ok := n.Properties["keywords"].([]any); ok {
			for _, k := range kw {
				if s, ok := k.(string); ok {
					keywords = append(keywords, s)
				}
			}
		}
		// Add name as keyword
		if name, ok := n.Properties["name"].(string); ok && name != "" {
			keywords = append(keywords, name)
		}

		nodes = append(nodes, ResponseNode{
			ID:       n.ID,
			Keywords: keywords,
			Response: response,
		})
	}

	s.responses = nodes
	log.Printf("Loaded %d response nodes from %s", len(nodes), path)
	return s
}

// WithClassifier sets a custom classifier function. The classifier receives
// the user's text and the available response nodes. It returns the IDs of the
// best matching nodes, or nil if no match.
//
// The classifier ONLY picks node IDs. It never generates response text.
// The default classifier does keyword matching. Replace with an LLM classifier
// for intelligent matching.
func (s *Server) WithClassifier(classifier Classifier) *Server {
	s.classifier = classifier
	return s
}

// WithFallbackClassifier sets an LLM-backed classifier called when the primary
// keyword classifier finds no match. Only used for the first 20 questions per
// session — after that, keyword matching only (zero API cost for abusive sessions).
func (s *Server) WithFallbackClassifier(classifier Classifier) *Server {
	s.fallbackClassifier = classifier
	return s
}

// WithNoMatch sets the response text when no node matches the user's question.
// This text is authored by the human, not generated by the LLM.
func (s *Server) WithNoMatch(text string) *Server {
	s.noMatchText = text
	return s
}

// WithContactFooter sets contact information appended to every response.
// Example: "For more help: hello@example.com | (555) 012-3456 | example.com"
func (s *Server) WithContactFooter(footer string) *Server {
	s.contactFooter = footer
	return s
}

// OnChat sets a simple text chat handler (legacy mode).
// DEPRECATED: This allows the handler to return arbitrary text, which means
// an LLM could generate hallucinated responses. Use WithResponses + WithClassifier
// for safe template-only responses where the LLM classifies but never composes.
func (s *Server) OnChat(handler ChatHandler) *Server {
	s.chatHandler = handler
	return s
}

// OnMessage sets a full message handler.
func (s *Server) OnMessage(handler MessageHandler) *Server {
	s.msgHandler = handler
	return s
}

// WithTRUG loads a .trug.json file as read-only chatbot context.
func (s *Server) WithTRUG(path string) *Server {
	data, err := os.ReadFile(path)
	if err != nil {
		log.Printf("warning: could not load TRUG %s: %v", path, err)
		return s
	}
	var trug map[string]any
	json.Unmarshal(data, &trug)
	s.trugData = trug
	return s
}

// WithLLM configures an LLM provider for classification. In v0.1.0, this
// stores the config. Use WithClassifier to provide an LLM-backed classifier.
func (s *Server) WithLLM(provider, model, apiKeyEnv string) *Server {
	s.llmConfig = &LLMConfig{Provider: provider, Model: model, APIKeyEnv: apiKeyEnv}
	return s
}

// WithUpstream connects to a TRUGS_PORT server for premium features (gateway mode).
func (s *Server) WithUpstream(addr, key string) *Server {
	s.upstreamAddr = addr
	s.upstreamKey = key
	return s
}

// Key returns the server's Noise keypair (useful for tests).
func (s *Server) Key() noise.DHKey {
	return s.key
}

// PublicKey returns the server's Noise public key as hex.
func (s *Server) PublicKey() string {
	return noise.KeyToHex(s.key.Public)
}

// GetTRUGContext returns a text summary of the loaded TRUG data.
func (s *Server) GetTRUGContext() string {
	return s.buildTRUGContext()
}

// GetResponses returns the loaded response nodes.
func (s *Server) GetResponses() []ResponseNode {
	return s.responses
}

func (s *Server) buildTRUGContext() string {
	if s.trugData == nil {
		return ""
	}
	nodes, ok := s.trugData["nodes"].([]any)
	if !ok {
		return ""
	}
	var ctx strings.Builder
	ctx.WriteString("Knowledge base:\n")
	for _, n := range nodes {
		node, ok := n.(map[string]any)
		if !ok {
			continue
		}
		props, _ := node["properties"].(map[string]any)
		name, _ := props["name"].(string)
		desc, _ := props["description"].(string)
		if name != "" {
			ctx.WriteString(fmt.Sprintf("- %s: %s\n", name, desc))
		}
	}
	return ctx.String()
}

// ── Default Classifier ───────────────────────────────────────────────────

// defaultClassifier does case-insensitive keyword matching.
// Replace with WithClassifier for LLM-powered classification.
func defaultClassifier(userText string, nodes []ResponseNode) []string {
	lower := strings.ToLower(userText)

	type scored struct {
		id    string
		score int
	}
	var matches []scored

	for _, node := range nodes {
		score := 0
		for _, kw := range node.Keywords {
			if strings.Contains(lower, strings.ToLower(kw)) {
				score++
			}
		}
		if score > 0 {
			matches = append(matches, scored{id: node.ID, score: score})
		}
	}

	if len(matches) == 0 {
		return nil
	}

	// Sort by score descending, return all matching IDs
	for i := 0; i < len(matches); i++ {
		for j := i + 1; j < len(matches); j++ {
			if matches[j].score > matches[i].score {
				matches[i], matches[j] = matches[j], matches[i]
			}
		}
	}

	ids := make([]string, len(matches))
	for i, m := range matches {
		ids[i] = m.id
	}
	return ids
}

// ── Server Lifecycle ─────────────────────────────────────────────────────

// ListenAndServe starts the server and blocks until SIGINT/SIGTERM.
func (s *Server) ListenAndServe() error {
	listener, err := noise.Listen(s.addr, s.key)
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}
	defer listener.Close()

	log.Printf("Noise Chatbot listening on %s", s.addr)
	log.Printf("Public key: %s", s.PublicKey())
	if len(s.responses) > 0 {
		log.Printf("Template mode: %d response nodes loaded (LLM classifies, never composes)", len(s.responses))
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		log.Println("shutting down...")
		cancel()
		listener.Close()
	}()

	for {
		conn, err := listener.Accept()
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			log.Printf("accept error: %v", err)
			continue
		}
		go s.serveConn(ctx, conn)
	}
}

// ServeListener serves on an existing Noise listener with the given context.
func (s *Server) ServeListener(ctx context.Context, listener *noise.Listener) error {
	go func() {
		<-ctx.Done()
		listener.Close()
	}()
	for {
		conn, err := listener.Accept()
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			continue
		}
		go s.serveConn(ctx, conn)
	}
}

func (s *Server) serveConn(ctx context.Context, conn *noise.NoiseConn) {
	defer conn.Close()

	// Check if this Noise key is banned
	keyHex := noise.KeyToHex(conn.RemoteIdentity())
	s.bannedMu.RLock()
	banTime, banned := s.bannedKeys[keyHex]
	s.bannedMu.RUnlock()
	if banned {
		// Permanent ban (honeypot tier 5) — never expires
		// Temporary ban (question limit) — expires after 3 days
		if banTime.IsZero() || time.Since(banTime) < 72*time.Hour {
			return // silently close
		}
		// Ban expired — remove and allow
		s.bannedMu.Lock()
		delete(s.bannedKeys, keyHex)
		s.bannedMu.Unlock()
	}

	stats := ConnectionStats{
		NodeHits:    make(map[string]int),
		ConnectedAt: time.Now(),
	}
	guardrailHits := 0    // tracks repeated guardrail triggers for honeypot
	questionCount := 0     // tracks total questions for natural wind-down

	var rateMu sync.Mutex
	messageTimestamps := make([]time.Time, 0)

	// Send greeting if configured
	if s.safety.Greeting != "" {
		greeting := protocol.Message{
			Type:    "CHAT",
			Payload: mustMarshalJSON(map[string]string{"text": s.safety.Greeting}),
			ID:      uuid.New().String(),
		}
		data, _ := json.Marshal(greeting)
		conn.Send(data)
	}

	for {
		if ctx.Err() != nil {
			return
		}

		// Session timeout
		if s.safety.SessionTimeout > 0 && !stats.LastMessageAt.IsZero() {
			if time.Since(stats.LastMessageAt) > s.safety.SessionTimeout {
				return
			}
		}

		data, err := conn.Receive()
		if err != nil {
			return
		}

		// Input size limit (bytes)
		if s.safety.MaxInputBytes > 0 && len(data) > s.safety.MaxInputBytes {
			resp := protocol.Message{
				Type:    "ERROR",
				Payload: mustMarshalJSON(map[string]string{"error": "message too large"}),
				ID:      uuid.New().String(),
			}
			respData, _ := json.Marshal(resp)
			conn.Send(respData)
			continue
		}

		// Rate limiting
		if s.safety.RateLimit > 0 {
			rateMu.Lock()
			now := time.Now()
			cutoff := now.Add(-1 * time.Minute)
			filtered := messageTimestamps[:0]
			for _, t := range messageTimestamps {
				if t.After(cutoff) {
					filtered = append(filtered, t)
				}
			}
			messageTimestamps = append(filtered, now)
			overLimit := len(messageTimestamps) > s.safety.RateLimit
			rateMu.Unlock()
			if overLimit {
				resp := protocol.Message{
					Type:    "ERROR",
					Payload: mustMarshalJSON(map[string]string{"error": "rate limit exceeded, please slow down"}),
					ID:      uuid.New().String(),
				}
				respData, _ := json.Marshal(resp)
				conn.Send(respData)
				continue
			}
		}

		stats.MessagesReceived++
		stats.LastMessageAt = time.Now()

		var msg protocol.Message
		if err := json.Unmarshal(data, &msg); err != nil {
			continue
		}

		// Token limit (approximate: 1 token ≈ 4 bytes)
		if msg.Type == "CHAT" && s.safety.MaxInputTokens > 0 {
			var req struct{ Text string `json:"text"` }
			json.Unmarshal(msg.Payload, &req)
			approxTokens := len(req.Text) / 4
			if approxTokens > s.safety.MaxInputTokens {
				resp := protocol.Message{
					Type:    "CHAT",
					Payload: mustMarshalJSON(map[string]string{"text": "Please keep your message shorter — I work best with concise questions."}),
					ID:      uuid.New().String(),
					ReplyTo: msg.ID,
				}
				respData, _ := json.Marshal(resp)
				conn.Send(respData)
				continue
			}
		}

		resp, matchedNodes, hitGuardrail := s.handleMessageFull(msg, questionCount)

		// Track analytics
		for _, id := range matchedNodes {
			stats.NodeHits[id]++
		}
		if len(matchedNodes) == 0 {
			stats.NoMatchCount++
		}

		// Count total questions (CHAT messages only)
		if msg.Type == "CHAT" {
			questionCount++
		}

		// Natural wind-down: after 20 questions, start slowing down.
		// A real user gets a helpful summary with links. An attacker gets tar-pitted.
		if questionCount >= 20 && !hitGuardrail && msg.Type == "CHAT" {
			// Slow down: 5 seconds per question after 20
			extraQuestions := questionCount - 20
			delay := time.Duration(extraQuestions) * 5 * time.Second
			if delay > 0 {
				time.Sleep(delay)
			}

			// At 40+: goodbye, close, 3-day temporary ban
			if questionCount >= 40 {
				farewell := protocol.Message{
					Type:    "CHAT",
					Payload: mustMarshalJSON(map[string]string{"text": "Thank you for chatting with us today! I hope I was able to help. For anything else, please visit our website or contact our team directly. Have a great day!"}),
					ID:      uuid.New().String(),
					ReplyTo: msg.ID,
				}
				farewellData, _ := json.Marshal(farewell)
				conn.Send(farewellData)

				// 3-day temporary ban — they can come back after
				s.bannedMu.Lock()
				s.bannedKeys[keyHex] = time.Now()
				s.bannedMu.Unlock()
				log.Printf("Temp-banned key %s for 3 days (40 questions reached)", keyHex[:16])

				return
			}

			// At exactly 20: offer a helpful summary with topics covered
			if questionCount == 20 {
				var topics []string
				for nodeID := range stats.NodeHits {
					for _, node := range s.responses {
						if node.ID == nodeID && len(node.Keywords) > 0 {
							topics = append(topics, node.Keywords[0])
							break
						}
					}
				}
				summary := "We've covered a lot! Here's what we discussed: "
				if len(topics) > 0 {
					summary += strings.Join(topics, ", ") + ". "
				}
				summary += "You can find more detail on all of these on our website. I'm still here if you have more questions!"

				resp = protocol.Message{
					Type:    "CHAT",
					Payload: mustMarshalJSON(map[string]string{"text": summary}),
					ID:      uuid.New().String(),
					ReplyTo: msg.ID,
				}
			}
			// After 20: normal answers continue, just slower.
			// A real user recognizes they have what they need and leaves.
			// An attacker thinks the slowness means they're making progress.
		}

		// Honeypot escalation: repeated guardrail hits.
		// Each tier gives different-sounding responses so the attacker thinks
		// they're making progress. They're not. They're wasting their time.
		// Response delay increases with each tier — looks like a slow server,
		// actually just wasting the attacker's time while freeing our resources.
		if hitGuardrail {
			guardrailHits++
		}
		if guardrailHits >= 3 {
			// Tier 2+: add delay. Looks like the server is "thinking" or "searching".
			// Tier 2 (3-4 hits): 3 seconds
			// Tier 3 (5-7 hits): 8 seconds
			// Tier 4 (8+ hits):  15 seconds
			var delay time.Duration
			switch {
			case guardrailHits >= 8:
				delay = 15 * time.Second
			case guardrailHits >= 5:
				delay = 8 * time.Second
			default:
				delay = 3 * time.Second
			}
			time.Sleep(delay)
		}
		if guardrailHits >= 12 {
			// Tier 5: goodbye. Ban the Noise key. Connection closed.
			farewell := protocol.Message{
				Type:    "CHAT",
				Payload: mustMarshalJSON(map[string]string{"text": "Thank you for chatting with us today! It looks like I've answered everything I can. Have a great day!"}),
				ID:      uuid.New().String(),
				ReplyTo: msg.ID,
			}
			farewellData, _ := json.Marshal(farewell)
			conn.Send(farewellData)

			// Ban this Noise public key — no future connections accepted
			keyHex := noise.KeyToHex(conn.RemoteIdentity())
			s.bannedMu.Lock()
			s.bannedKeys[keyHex] = time.Now()
			s.bannedMu.Unlock()
			log.Printf("Banned key %s (honeypot tier 5 — repeated probing)", keyHex[:16])

			return // close connection
		} else if guardrailHits >= 8 {
			// Tier 4: loops back to seeming helpful — endless cycle
			honeypot := []string{
				"Actually, let me check on that for you... I think there might be something in our system. Can you be more specific about what you need?",
				"Interesting question. I'm seeing some related information but I need to verify. What exactly are you looking for?",
				"I may have found something. Could you rephrase your question so I can give you the right answer?",
				"Let me look into that further. In the meantime, is there a specific part of our service you're asking about?",
			}
			resp = protocol.Message{
				Type:    "CHAT",
				Payload: mustMarshalJSON(map[string]string{"text": honeypot[guardrailHits%len(honeypot)]}),
				ID:      uuid.New().String(),
				ReplyTo: msg.ID,
			}
		} else if guardrailHits >= 5 {
			// Tier 3: seems like they're getting warmer — they're not
			honeypot := []string{
				"Hmm, that's an interesting angle. I'm not sure I can share that directly, but let me see what I can find...",
				"You're asking the right questions. Unfortunately my access level doesn't cover that area. Have you tried our help center?",
				"I think I understand what you're looking for. Let me check if there's a public resource for that...",
			}
			resp = protocol.Message{
				Type:    "CHAT",
				Payload: mustMarshalJSON(map[string]string{"text": honeypot[guardrailHits%len(honeypot)]}),
				ID:      uuid.New().String(),
				ReplyTo: msg.ID,
			}
		} else if guardrailHits >= 3 {
			// Tier 2: slightly different answers — looks like different system responses
			honeypot := []string{
				"I appreciate your patience. That's outside my current scope, but I'm happy to help with product questions.",
				"Good question — unfortunately that falls under a different department. Can I help with something else?",
				"I've noted your request. For that type of inquiry, our team would need to assist you directly.",
			}
			resp = protocol.Message{
				Type:    "CHAT",
				Payload: mustMarshalJSON(map[string]string{"text": honeypot[guardrailHits%len(honeypot)]}),
				ID:      uuid.New().String(),
				ReplyTo: msg.ID,
			}
		}
		// Tier 1 (hits 1-2): normal guardrail response (already set above)

		// Analytics callback
		if s.onAnalytics != nil {
			var req struct{ Text string `json:"text"` }
			json.Unmarshal(msg.Payload, &req)
			s.onAnalytics(stats, req.Text, matchedNodes)
		}

		respData, _ := json.Marshal(resp)
		if err := conn.Send(respData); err != nil {
			return
		}
	}
}

func mustMarshalJSON(v any) json.RawMessage {
	b, _ := json.Marshal(v)
	return b
}

// handleMessage is the legacy entry point (no stats). Used by tests.
func (s *Server) handleMessage(msg protocol.Message) protocol.Message {
	resp, _, _ := s.handleMessageFull(msg, 0)
	return resp
}

// handleMessageWithStats is called from serveConn with question count.
func (s *Server) handleMessageWithStats(msg protocol.Message) (protocol.Message, []string, bool) {
	return s.handleMessageFull(msg, 0)
}

// handleMessageFull returns the response, matched node IDs, and whether a guardrail was hit.
// questionCount controls whether the LLM fallback classifier is used (disabled after 20).
func (s *Server) handleMessageFull(msg protocol.Message, questionCount int) (protocol.Message, []string, bool) {
	// Full message handler takes priority
	if s.msgHandler != nil {
		return s.msgHandler(msg), nil, false
	}

	if msg.Type == "CHAT" {
		var req struct {
			Text string `json:"text"`
		}
		json.Unmarshal(msg.Payload, &req)

		var responseText string
		var matchedNodes []string
		hitGuardrail := false

		classify := s.classifier
		if classify == nil {
			classify = defaultClassifier
		}

		// Check guardrails FIRST — boundary questions get pre-authored friendly answers
		if len(s.guardrails) > 0 {
			guardIDs := classify(req.Text, s.guardrails)
			if len(guardIDs) > 0 {
				hitGuardrail = true
				matchedNodes = guardIDs
				// Return first guardrail match verbatim
				for _, node := range s.guardrails {
					if node.ID == guardIDs[0] {
						responseText = node.Response
						break
					}
				}
			}
		}

		// If no guardrail matched, check business responses
		if responseText == "" && len(s.responses) > 0 {
			nodeIDs := classify(req.Text, s.responses)

			// If keywords didn't match and we have a fallback LLM classifier,
			// use it — but only for the first 20 questions (zero API cost after)
			if len(nodeIDs) == 0 && s.fallbackClassifier != nil && questionCount <= 20 {
				nodeIDs = s.fallbackClassifier(req.Text, s.responses)
			}

			matchedNodes = nodeIDs

			if len(nodeIDs) == 0 {
				responseText = s.noMatchText
			} else {
				// Build response by concatenating matched nodes' text VERBATIM
				responseIndex := make(map[string]string)
				for _, node := range s.responses {
					responseIndex[node.ID] = node.Response
				}
				var parts []string
				for _, id := range nodeIDs {
					if text, ok := responseIndex[id]; ok {
						parts = append(parts, text)
					}
				}
				if len(parts) == 0 {
					responseText = s.noMatchText
				} else {
					responseText = strings.Join(parts, "\n\n")
				}
			}
		} else if responseText == "" && s.chatHandler != nil {
			// Legacy mode: handler returns arbitrary text (deprecated)
			responseText = s.chatHandler(req.Text)
		} else if responseText == "" {
			// No handler, no responses: echo
			responseText = req.Text
		}

		// Format response: [count] echo question + answer + contact footer
		formattedResponse := responseText
		if questionCount > 0 {
			// Repeat the question so it reads like a FAQ
			formattedResponse = fmt.Sprintf("[%d] You asked about: %s\n\n%s", questionCount, req.Text, responseText)
		}
		if s.contactFooter != "" {
			formattedResponse += "\n\n" + s.contactFooter
		}

		payload, _ := json.Marshal(map[string]string{"text": formattedResponse})
		return protocol.Message{
			Type:    "CHAT",
			Payload: payload,
			ID:      uuid.New().String(),
			ReplyTo: msg.ID,
		}, matchedNodes, hitGuardrail
	}

	// Default echo for non-CHAT messages
	return protocol.Message{
		Type:    msg.Type,
		Payload: msg.Payload,
		ID:      uuid.New().String(),
		ReplyTo: msg.ID,
	}, nil, false
}
