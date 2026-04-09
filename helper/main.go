// noise-helper is a stdin/stdout bridge for Noise_IK encrypted communication.
//
// Usage: noise-helper --server HOST:PORT --key SERVER_PUB_HEX
//
// Protocol:
//   - Performs Noise_IK handshake on startup
//   - Reads JSON lines from stdin -> encrypts -> sends to server
//   - Receives from server -> decrypts -> writes JSON lines to stdout
//   - Prints "CONNECTED" to stdout after successful handshake
//   - Prints "ERROR: ..." to stderr on failure
package main

// <trl>
// DEFINE "helper" AS PROCESS.
// PROCESS helper READS RECORD message FROM ENTRY stdin THEN SEND TO ENDPOINT server.
// PROCESS helper READS RECORD message FROM ENDPOINT server THEN WRITE TO EXIT stdout.
// EACH RECORD message SHALL ENCRYPT 'with RECORD noise_ik.
// </trl>

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/TRUGS-LLC/noise-chatbot/noise"
)

func main() {
	server := flag.String("server", "localhost:9090", "server address (host:port)")
	keyHex := flag.String("key", "", "server public key (hex)")
	flag.Parse()

	if *keyHex == "" {
		fmt.Fprintln(os.Stderr, "ERROR: --key required")
		os.Exit(1)
	}

	serverPub, err := noise.HexToKey(*keyHex)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: invalid key: %v\n", err)
		os.Exit(1)
	}

	// Generate client keypair
	clientKey, err := noise.GenerateKeypair()
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: keygen: %v\n", err)
		os.Exit(1)
	}

	// Connect and handshake
	conn, err := noise.Dial(*server, clientKey, serverPub)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: connect: %v\n", err)
		os.Exit(1)
	}
	defer conn.Close()

	// Signal success
	fmt.Println("CONNECTED")

	// Start reader goroutine: server -> stdout
	go func() {
		for {
			data, err := conn.Receive()
			if err != nil {
				fmt.Fprintf(os.Stderr, "ERROR: recv: %v\n", err)
				os.Exit(0)
			}
			// Write as single line to stdout
			os.Stdout.Write(data)
			os.Stdout.Write([]byte("\n"))
		}
	}()

	// Main loop: stdin -> server
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 16*1024*1024), 16*1024*1024) // 16MB max
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		// Validate it's JSON
		if !json.Valid(line) {
			fmt.Fprintf(os.Stderr, "ERROR: invalid JSON on stdin\n")
			continue
		}
		if err := conn.Send(line); err != nil {
			fmt.Fprintf(os.Stderr, "ERROR: send: %v\n", err)
			os.Exit(1)
		}
	}
}
