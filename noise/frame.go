package noise

import (
	"encoding/binary"
	"fmt"
	"io"
	"net"
)

// writeFrame writes a length-prefixed frame to a connection.
func writeFrame(conn net.Conn, data []byte) error {
	length := uint32(len(data))
	if err := binary.Write(conn, binary.BigEndian, length); err != nil {
		return fmt.Errorf("write frame length: %w", err)
	}
	if _, err := conn.Write(data); err != nil {
		return fmt.Errorf("write frame data: %w", err)
	}
	return nil
}

// readFrame reads a length-prefixed frame from a connection.
func readFrame(conn net.Conn) ([]byte, error) {
	var length uint32
	if err := binary.Read(conn, binary.BigEndian, &length); err != nil {
		return nil, fmt.Errorf("read frame length: %w", err)
	}
	// Handshake messages are small — cap at 65536 bytes
	if length > 65536 {
		return nil, fmt.Errorf("frame too large: %d bytes", length)
	}
	data := make([]byte, length)
	if _, err := io.ReadFull(conn, data); err != nil {
		return nil, fmt.Errorf("read frame data: %w", err)
	}
	return data, nil
}
