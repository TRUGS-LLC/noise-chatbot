package main

import (
	"fmt"

	"github.com/TRUGS-LLC/noise-chatbot/server"
)

func main() {
	s := server.New(":9090")
	s.OnChat(func(text string) string {
		return "You said: " + text
	})
	fmt.Println("Echo chatbot running on :9090")
	fmt.Println("Public key:", s.PublicKey())
	s.ListenAndServe()
}
