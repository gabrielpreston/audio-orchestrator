package main

import (
	"context"
	"encoding/json"
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

	// Simple HTTP registration endpoint used by services that attempt an
	// HTTP-based register before falling back to WebSocket. This accepts a
	// small JSON object {name, url, description} and responds 200 on success.
	http.HandleFunc("/mcp/register", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		// Accept body but we don't need to persist registrations in this
		// simple server; just validate some JSON and return 200.
		type regReq struct {
			Name        string `json:"name"`
			URL         string `json:"url"`
			Description string `json:"description"`
		}
		var req regReq
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte("invalid json"))
			return
		}
		// Very small validation
		if req.Name == "" || req.URL == "" {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte("name and url required"))
			return
		}
		w.WriteHeader(http.StatusOK)
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
