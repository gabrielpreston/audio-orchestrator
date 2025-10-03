package main

import (
	"context"
	"time"

	"github.com/gorilla/websocket"
	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

type wsTransport struct{ conn *websocket.Conn }

func (t *wsTransport) Connect(ctx context.Context) (mcp.Connection, error) {
	return &wsConnection{conn: t.conn}, nil
}

type wsConnection struct{ conn *websocket.Conn }

func (w *wsConnection) Read(ctx context.Context) (jsonrpc.Message, error) {
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
	if dl, ok := ctx.Deadline(); ok {
		_ = w.conn.SetWriteDeadline(dl)
		defer w.conn.SetWriteDeadline(time.Time{})
	}
	return w.conn.WriteMessage(websocket.BinaryMessage, data)
}

func (w *wsConnection) Close() error      { return w.conn.Close() }
func (w *wsConnection) SessionID() string { return "" }

func NewWebSocketTransport(conn *websocket.Conn) mcp.Transport {
	return &wsTransport{conn: conn}
}
