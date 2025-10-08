package mcp

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

type wsServerTransport struct {
	conn *websocket.Conn
}

type wsServerConnection struct {
	conn *websocket.Conn
}

func (t *wsServerTransport) Connect(ctx context.Context) (sdk.Connection, error) {
	return &wsServerConnection{conn: t.conn}, nil
}

func (c *wsServerConnection) Read(ctx context.Context) (jsonrpc.Message, error) {
	if dl, ok := ctx.Deadline(); ok {
		_ = c.conn.SetReadDeadline(dl)
		defer c.conn.SetReadDeadline(time.Time{})
	}
	_, data, err := c.conn.ReadMessage()
	if err != nil {
		return nil, err
	}
	return jsonrpc.DecodeMessage(data)
}

func (c *wsServerConnection) Write(ctx context.Context, msg jsonrpc.Message) error {
	data, err := jsonrpc.EncodeMessage(msg)
	if err != nil {
		return err
	}
	if dl, ok := ctx.Deadline(); ok {
		_ = c.conn.SetWriteDeadline(dl)
		defer c.conn.SetWriteDeadline(time.Time{})
	}
	return c.conn.WriteMessage(websocket.BinaryMessage, data)
}

func (c *wsServerConnection) Close() error {
	return c.conn.Close()
}

func (c *wsServerConnection) SessionID() string { return "" }

func TestClientWrapperConnectWebSocket(t *testing.T) {
	serverImpl := sdk.NewServer(&sdk.Implementation{Name: "ws-server", Version: "1.0.0"}, nil)

	type echoArgs struct {
		Message string `json:"message"`
	}

	sdk.AddTool(serverImpl, &sdk.Tool{Name: "echo", Description: "echo back messages"}, func(ctx context.Context, req *sdk.CallToolRequest, args echoArgs) (*sdk.CallToolResult, any, error) {
		return &sdk.CallToolResult{
			Content: []sdk.Content{
				&sdk.TextContent{Text: args.Message},
			},
		}, nil, nil
	})

	upgrader := websocket.Upgrader{CheckOrigin: func(*http.Request) bool { return true }}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/ws" {
			http.NotFound(w, r)
			return
		}
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Logf("upgrade failed: %v", err)
			return
		}
		go func() {
			transport := &wsServerTransport{conn: conn}
			session, err := serverImpl.Connect(context.Background(), transport, nil)
			if err != nil {
				t.Logf("server connect failed: %v", err)
				_ = conn.Close()
				return
			}
			defer func() {
				if err := session.Close(); err != nil {
					t.Logf("server session close: %v", err)
				}
			}()
			if err := session.Wait(); err != nil {
				t.Logf("server session wait: %v", err)
			}
		}()
	}))
	defer srv.Close()

	wsURL := "ws" + srv.URL[len("http"):]
	wsURL += "/ws"

	wrapper := NewClientWrapper("integration-client", "test")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := wrapper.ConnectWebSocket(ctx, wsURL); err != nil {
		t.Fatalf("ConnectWebSocket failed: %v", err)
	}
	t.Cleanup(func() { _ = wrapper.Close() })

	if wrapper.session == nil {
		t.Fatal("session not initialized")
	}

	callCtx, callCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer callCancel()

	res, err := wrapper.session.CallTool(callCtx, &sdk.CallToolParams{
		Name:      "echo",
		Arguments: map[string]any{"message": "hello"},
	})
	if err != nil {
		t.Fatalf("CallTool failed: %v", err)
	}
	if len(res.Content) != 1 {
		t.Fatalf("expected 1 content item, got %d", len(res.Content))
	}
	text, ok := res.Content[0].(*sdk.TextContent)
	if !ok {
		t.Fatalf("unexpected content type %T", res.Content[0])
	}
	if text.Text != "hello" {
		t.Fatalf("expected echo response 'hello', got %q", text.Text)
	}
}

func TestClientWrapperConnectCommand(t *testing.T) {
	binPath := buildCommandServer(t)

	wrapper := NewClientWrapper("integration-client", "test")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := wrapper.ConnectCommand(ctx, "cmd-server", binPath, nil, nil); err != nil {
		t.Fatalf("ConnectCommand failed: %v", err)
	}
	t.Cleanup(func() { _ = wrapper.Close() })

	callCtx, callCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer callCancel()

	res, err := wrapper.session.CallTool(callCtx, &sdk.CallToolParams{
		Name:      "echo",
		Arguments: map[string]any{"message": "integration"},
	})
	if err != nil {
		t.Fatalf("CallTool failed: %v", err)
	}
	if len(res.Content) != 1 {
		t.Fatalf("expected 1 content item, got %d", len(res.Content))
	}
	text, ok := res.Content[0].(*sdk.TextContent)
	if !ok {
		t.Fatalf("unexpected content type %T", res.Content[0])
	}
	if text.Text != "integration" {
		t.Fatalf("expected echo response 'integration', got %q", text.Text)
	}
}

func buildCommandServer(t *testing.T) string {
	t.Helper()
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("failed to determine caller")
	}
	pkgDir := filepath.Dir(filename)
	serverDir := filepath.Join(pkgDir, "testdata", "cmdserver")

	binPath := filepath.Join(t.TempDir(), "cmdserver")
	cmd := exec.Command("go", "build", "-o", binPath, ".")
	cmd.Dir = serverDir
	if output, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("go build failed: %v\n%s", err, output)
	}
	return binPath
}
