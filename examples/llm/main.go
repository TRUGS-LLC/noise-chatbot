package main

import (
	"fmt"

	"github.com/TRUGS-LLC/noise-chatbot/server"
)

func main() {
	s := server.New(":9090")
	s.WithLLM("anthropic", "claude-haiku-4-5", "ANTHROPIC_API_KEY")
	s.OnChat(func(text string) string {
		// The server's LLM integration handles this
		// For now, return a placeholder until LLM client is wired
		return "LLM integration coming soon. You asked: " + text
	})
	fmt.Println("LLM chatbot running on :9090")
	fmt.Println("Public key:", s.PublicKey())
	s.ListenAndServe()
}
