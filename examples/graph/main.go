package main

import (
	"fmt"

	"github.com/TRUGS-LLC/noise-chatbot/server"
)

func main() {
	s := server.New(":9090")
	s.WithTRUG("knowledge.trug.json")
	s.OnChat(func(text string) string {
		return "Graph-backed response coming soon. You asked: " + text
	})
	fmt.Println("Graph chatbot running on :9090")
	fmt.Println("Public key:", s.PublicKey())
	s.ListenAndServe()
}
