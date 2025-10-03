package mcp

import (
	"context"
	"time"

	"github.com/gorilla/websocket"
	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

// wsTransport implements sdk.Transport for a single websocket.Conn.
type wsTransport struct {
	conn *websocket.Conn
}

func (t *wsTransport) Connect(ctx context.Context) (sdk.Connection, error) {
	return &wsConnection{conn: t.conn}, nil
}

// wsConnection implements sdk.Connection over a websocket.Conn.
type wsConnection struct {
	conn *websocket.Conn
}

func (w *wsConnection) Read(ctx context.Context) (jsonrpc.Message, error) {
	// respect context by setting a read deadline when context has a deadline
	if dl, ok := ctx.Deadline(); ok {
		_ = w.conn.SetReadDeadline(dl)
		defer w.conn.SetReadDeadline(time.Time{})
	}
	_, data, err := w.conn.ReadMessage()
	if err != nil {
		return nil, err
	}
	return jsonrpc.DecodeMessage(data)
}

func (w *wsConnection) Write(ctx context.Context, msg jsonrpc.Message) error {
	data, err := jsonrpc.EncodeMessage(msg)
	if err != nil {
		return err
	}
	// respect context deadline by setting a write deadline
	if dl, ok := ctx.Deadline(); ok {
		_ = w.conn.SetWriteDeadline(dl)
		defer w.conn.SetWriteDeadline(time.Time{})
	}
	return w.conn.WriteMessage(websocket.BinaryMessage, data)
}

func (w *wsConnection) Close() error { return w.conn.Close() }

func (w *wsConnection) SessionID() string { return "" }

func newClientWebSocketTransport(conn *websocket.Conn) sdk.Transport {
	return &wsTransport{conn: conn}
}
