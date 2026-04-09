package server

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/TRUGS-LLC/noise-chatbot/noise"
	"github.com/TRUGS-LLC/noise-chatbot/protocol"
	"github.com/google/uuid"
)

// ChatHandler is the simple text chat callback.
type ChatHandler func(text string) string

// MessageHandler is the full message callback.
type MessageHandler func(msg protocol.Message) protocol.Message

// Server is an encrypted chatbot server using Noise_IK.
type Server struct {
	addr         string
	key          noise.DHKey
	chatHandler  ChatHandler
	msgHandler   MessageHandler
	trugData     map[string]any
	llmConfig    *LLMConfig
	upstreamAddr string
	upstreamKey  string
}

// LLMConfig configures an LLM provider for chat responses.
type LLMConfig struct {
	Provider  string // "anthropic" or "openai"
	Model     string
	APIKeyEnv string
}

// New creates a new Noise Chatbot server.
func New(addr string) *Server {
	key, _ := noise.GenerateKeypair()
	return &Server{addr: addr, key: key}
}

// OnChat sets a simple text chat handler.
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

// WithLLM configures an LLM provider for chat responses.
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

// PublicKey returns the server's Noise public key as hex.
func (s *Server) PublicKey() string {
	return noise.KeyToHex(s.key.Public)
}

// ListenAndServe starts the server and blocks until SIGINT/SIGTERM.
func (s *Server) ListenAndServe() error {
	listener, err := noise.Listen(s.addr, s.key)
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}
	defer listener.Close()

	log.Printf("Noise Chatbot listening on %s", s.addr)
	log.Printf("Public key: %s", s.PublicKey())

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

func (s *Server) serveConn(ctx context.Context, conn *noise.NoiseConn) {
	defer conn.Close()
	for {
		if ctx.Err() != nil {
			return
		}
		data, err := conn.Receive()
		if err != nil {
			return
		}
		var msg protocol.Message
		if err := json.Unmarshal(data, &msg); err != nil {
			continue
		}
		resp := s.handleMessage(msg)
		respData, _ := json.Marshal(resp)
		if err := conn.Send(respData); err != nil {
			return
		}
	}
}

func (s *Server) handleMessage(msg protocol.Message) protocol.Message {
	// Full message handler takes priority
	if s.msgHandler != nil {
		return s.msgHandler(msg)
	}

	// Simple chat handler
	if msg.Type == "CHAT" && s.chatHandler != nil {
		var req struct {
			Text string `json:"text"`
		}
		json.Unmarshal(msg.Payload, &req)

		responseText := s.chatHandler(req.Text)
		payload, _ := json.Marshal(map[string]string{"text": responseText})
		return protocol.Message{
			Type:    "CHAT",
			Payload: payload,
			ID:      uuid.New().String(),
			ReplyTo: msg.ID,
		}
	}

	// Default echo
	return protocol.Message{
		Type:    msg.Type,
		Payload: msg.Payload,
		ID:      uuid.New().String(),
		ReplyTo: msg.ID,
	}
}
