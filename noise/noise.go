package noise

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"

	noiselib "github.com/flynn/noise"
)

// DHKey is a Noise static keypair (re-exported from flynn/noise).
type DHKey = noiselib.DHKey

// CipherSuite is the Noise cipher suite used for all connections:
// Curve25519 for DH, ChaChaPoly for encryption, BLAKE2b for hashing.
var CipherSuite = noiselib.NewCipherSuite(
	noiselib.DH25519,
	noiselib.CipherChaChaPoly,
	noiselib.HashBLAKE2b,
)

// GenerateKeypair generates a new Curve25519 static keypair for Noise.
func GenerateKeypair() (noiselib.DHKey, error) {
	return CipherSuite.GenerateKeypair(rand.Reader)
}

// KeyToHex encodes a public key as a hex string.
func KeyToHex(key []byte) string {
	return hex.EncodeToString(key)
}

// HexToKey decodes a hex string into a public key.
func HexToKey(s string) ([]byte, error) {
	b, err := hex.DecodeString(s)
	if err != nil {
		return nil, fmt.Errorf("invalid hex key: %w", err)
	}
	if len(b) != 32 {
		return nil, fmt.Errorf("key must be 32 bytes, got %d", len(b))
	}
	return b, nil
}
