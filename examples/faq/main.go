package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/TRUGS-LLC/noise-chatbot/server"
)

func main() {
	// Load FAQ from JSON file
	data, _ := os.ReadFile("faq.json")
	var faq map[string]string
	json.Unmarshal(data, &faq)

	s := server.New(":9090")
	s.OnChat(func(text string) string {
		lower := strings.ToLower(text)
		for q, a := range faq {
			if strings.Contains(lower, strings.ToLower(q)) {
				return a
			}
		}
		return "I don't have an answer for that. Try asking about: " + joinKeys(faq)
	})
	fmt.Println("FAQ chatbot running on :9090")
	fmt.Println("Public key:", s.PublicKey())
	s.ListenAndServe()
}

func joinKeys(m map[string]string) string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return strings.Join(keys, ", ")
}
