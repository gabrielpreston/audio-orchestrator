package main

import (
	"context"
	"log"
	"net/http"
	"os"

	"github.com/gorilla/websocket"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	// Create a simple MCP server with no special tools.
	server := mcp.NewServer(&mcp.Implementation{Name: "mcp-server", Version: "v0.0.0"}, nil)

	// Simple HTTP health endpoint
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok"))
	})

	upgrader := websocket.Upgrader{}
	// WebSocket endpoint to accept MCP connections. Each WS is bridged to an
	// SDK Transport by wrapping the WS as an io.ReadWriteCloser.
	http.HandleFunc("/mcp/ws", func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Printf("ws upgrade failed: %v", err)
			return
		}
		// Wrap ws and create a transport that returns a Connection using the
		// SDK's InMemoryTransport pattern via a custom wrapper.
		t := NewWebSocketTransport(conn)
		// Use SDK connect helper to bind the transport to the server handler.
		go func() {
			// Connect the server over the transport. Server.Connect starts handling
			// messages and returns a connection object that can be used to Close or
			// Wait for client termination.
			conn, err := server.Connect(context.Background(), t, nil)
			if err != nil {
				log.Printf("mcp server connect error: %v", err)
				return
			}
			// Wait for the client to disconnect (or for the connection to be closed).
			if err := conn.Wait(); err != nil {
				log.Printf("mcp server session ended with error: %v", err)
			} else {
				log.Printf("mcp server session ended")
			}
		}()
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "9001"
	}
	log.Printf("mcp server listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
