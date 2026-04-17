// Parity test harness.
//
// Reads a JSON configuration on stdin describing which server features to
// enable, starts a noise-chatbot server on an ephemeral port, and prints
// exactly one line to stdout:
//
//	READY host:port pubkey_hex
//
// Then serves on the listener until killed (SIGINT / SIGTERM).
//
// Used by REFERENCE/parity/runner.py to exercise fixtures against the Go
// golden implementation.
//
// Build:
//
//	cd ~/REPO/noise-chatbot
//	cp REFERENCE/parity/harness/main.go tests/parity/harness/main.go
//	go build -o /tmp/parity-harness ./tests/parity/harness
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/TRUGS-LLC/noise-chatbot/noise"
	"github.com/TRUGS-LLC/noise-chatbot/server"
)

type Config struct {
	Addr string `json:"addr,omitempty"`

	Responses    []server.ResponseNode `json:"responses,omitempty"`
	NoMatchText  string                `json:"no_match_text,omitempty"`
	Greeting     string                `json:"greeting,omitempty"`
	ContactFooter string               `json:"contact_footer,omitempty"`

	// Extra guardrails appended to the default 15 via WithGuardrails path.
	ExtraGuardrails []server.ResponseNode `json:"extra_guardrails,omitempty"`

	// Legacy OnChat handler kind: "echo" (returns "You said: "+text),
	// "prefix" (returns PrefixText+text), "" (none — default echo when no
	// responses are configured).
	ChatHandler string `json:"chat_handler,omitempty"`
	PrefixText  string `json:"prefix_text,omitempty"`

	// Safety overrides. RawSafety=true → fields used verbatim (0 = unlimited).
	// RawSafety=false and any non-zero field → patched onto default safety.
	MaxInputTokens        int  `json:"max_input_tokens,omitempty"`
	MaxInputBytes         int  `json:"max_input_bytes,omitempty"`
	RateLimit             int  `json:"rate_limit,omitempty"`
	SessionTimeoutSeconds int  `json:"session_timeout_seconds,omitempty"`
	RawSafety             bool `json:"raw_safety,omitempty"`
}

func main() {
	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read stdin: %v\n", err)
		os.Exit(2)
	}
	var cfg Config
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &cfg); err != nil {
			fmt.Fprintf(os.Stderr, "parse config: %v\n", err)
			os.Exit(2)
		}
	}

	addr := cfg.Addr
	if addr == "" {
		addr = "127.0.0.1:0"
	}

	s := server.New(addr)

	if cfg.RawSafety {
		s.WithSafety(server.SafetyConfig{
			MaxInputTokens: cfg.MaxInputTokens,
			MaxInputBytes:  cfg.MaxInputBytes,
			RateLimit:      cfg.RateLimit,
			SessionTimeout: time.Duration(cfg.SessionTimeoutSeconds) * time.Second,
		})
	} else if cfg.MaxInputTokens != 0 || cfg.MaxInputBytes != 0 ||
		cfg.RateLimit != 0 || cfg.SessionTimeoutSeconds != 0 {
		safety := server.SafetyConfig{
			MaxInputTokens: 200,
			MaxInputBytes:  2000,
			RateLimit:      30,
			SessionTimeout: 30 * time.Minute,
			ConfidenceMin:  1,
		}
		if cfg.MaxInputTokens != 0 {
			safety.MaxInputTokens = cfg.MaxInputTokens
		}
		if cfg.MaxInputBytes != 0 {
			safety.MaxInputBytes = cfg.MaxInputBytes
		}
		if cfg.RateLimit != 0 {
			safety.RateLimit = cfg.RateLimit
		}
		if cfg.SessionTimeoutSeconds != 0 {
			safety.SessionTimeout = time.Duration(cfg.SessionTimeoutSeconds) * time.Second
		}
		s.WithSafety(safety)
	}

	if cfg.ExtraGuardrails != nil {
		s.WithGuardrails(writeTempGuardrailsTRUG(cfg.ExtraGuardrails))
	}
	if cfg.Responses != nil {
		s.WithResponses(cfg.Responses)
	}
	if cfg.NoMatchText != "" {
		s.WithNoMatch(cfg.NoMatchText)
	}
	if cfg.Greeting != "" {
		s.WithGreeting(cfg.Greeting)
	}
	if cfg.ContactFooter != "" {
		s.WithContactFooter(cfg.ContactFooter)
	}

	switch cfg.ChatHandler {
	case "echo":
		s.OnChat(func(text string) string { return "You said: " + text })
	case "prefix":
		s.OnChat(func(text string) string { return cfg.PrefixText + text })
	}

	listener, err := noise.Listen(addr, s.Key())
	if err != nil {
		fmt.Fprintf(os.Stderr, "listen: %v\n", err)
		os.Exit(3)
	}
	bound := listener.Addr().(*net.TCPAddr)
	hostPort := fmt.Sprintf("127.0.0.1:%d", bound.Port)
	fmt.Printf("READY %s %s\n", hostPort, s.PublicKey())
	os.Stdout.Sync()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		cancel()
		listener.Close()
	}()

	if err := s.ServeListener(ctx, listener); err != nil {
		fmt.Fprintf(os.Stderr, "serve: %v\n", err)
		os.Exit(4)
	}
}

// writeTempGuardrailsTRUG serialises the provided guardrails as a minimal
// guardrails.trug.json blob and returns the temp-file path.
func writeTempGuardrailsTRUG(nodes []server.ResponseNode) string {
	tmp, err := os.CreateTemp("", "parity_guardrails_*.trug.json")
	if err != nil {
		fmt.Fprintf(os.Stderr, "temp guardrails: %v\n", err)
		os.Exit(5)
	}
	type props struct {
		Response string   `json:"response"`
		Keywords []string `json:"keywords"`
	}
	type node struct {
		ID         string `json:"id"`
		Properties props  `json:"properties"`
	}
	out := struct {
		Nodes []node `json:"nodes"`
	}{}
	for _, n := range nodes {
		out.Nodes = append(out.Nodes, node{
			ID:         n.ID,
			Properties: props{Response: n.Response, Keywords: n.Keywords},
		})
	}
	data, _ := json.Marshal(out)
	tmp.Write(data)
	tmp.Close()
	return tmp.Name()
}
