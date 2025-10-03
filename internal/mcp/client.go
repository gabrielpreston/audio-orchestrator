package mcp

import (
	"context"
	"log"
	"net/url"
	"time"

	"github.com/gorilla/websocket"
	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

// ClientWrapper provides a small helper to connect to an MCP server over
// websocket and manage the client session lifecycle.
type ClientWrapper struct {
	client  *sdk.Client
	session *sdk.ClientSession
}

// NewClientWrapper creates a new wrapper with the given name/version.
func NewClientWrapper(name, version string) *ClientWrapper {
	impl := &sdk.Implementation{Name: name, Version: version}
	c := sdk.NewClient(impl, nil)
	return &ClientWrapper{client: c}
}

// ConnectWebSocket connects to the MCP server websocket endpoint and creates a session.
func (w *ClientWrapper) ConnectWebSocket(ctx context.Context, rawurl string) error {
	u, err := url.Parse(rawurl)
	if err != nil {
		return err
	}
	// Ensure ws scheme
	if u.Scheme != "ws" && u.Scheme != "wss" {
		if u.Scheme == "http" {
			u.Scheme = "ws"
		}
		if u.Scheme == "https" {
			u.Scheme = "wss"
		}
	}
	dialer := websocket.DefaultDialer
	// Connect
	conn, _, err := dialer.DialContext(ctx, u.String(), nil)
	if err != nil {
		return err
	}
	// Wrap connection into io.ReadWriteCloser and use sdk.IOTransport
	t := newClientWebSocketTransport(conn)
	// Connect client
	sess, err := w.client.Connect(ctx, t, nil)
	if err != nil {
		return err
	}
	w.session = sess
	// Start optional keepalive ping using SDK's Ping if desired
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				_ = sess.Ping(context.Background(), nil)
			}
		}
	}()
	log.Printf("mcp client connected to %s", rawurl)
	return nil
}

func (w *ClientWrapper) Close() error {
	if w.session != nil {
		_ = w.session.Close()
	}
	return nil
}
