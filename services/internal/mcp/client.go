package mcp

import (
	"bufio"
	"context"
	"errors"
	"log"
	"net/url"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

// ClientWrapper provides a small helper to connect to an MCP server over
// websocket or command transports and manage the client session lifecycle.
type ClientWrapper struct {
	client          *sdk.Client
	session         *sdk.ClientSession
	keepaliveCancel context.CancelFunc
	closers         []func() error
	mu              sync.Mutex
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
	if u.Scheme != "ws" && u.Scheme != "wss" {
		if u.Scheme == "http" {
			u.Scheme = "ws"
		}
		if u.Scheme == "https" {
			u.Scheme = "wss"
		}
	}
	dialer := websocket.DefaultDialer
	conn, _, err := dialer.DialContext(ctx, u.String(), nil)
	if err != nil {
		return err
	}
	t := newClientWebSocketTransport(conn)
	if err := w.connect(ctx, t); err != nil {
		_ = conn.Close()
		return err
	}
	log.Printf("mcp client connected to %s", rawurl)
	return nil
}

// ConnectCommand spawns a local MCP server process and connects via stdio.
func (w *ClientWrapper) ConnectCommand(ctx context.Context, serverName, command string, args []string, env map[string]string) error {
	if command == "" {
		return errors.New("command is required")
	}
	cmd := exec.Command(command, args...)
	if len(env) > 0 {
		merged := os.Environ()
		for k, v := range env {
			merged = append(merged, k+"="+v)
		}
		cmd.Env = merged
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	stdin, err := cmd.StdinPipe()
	if err != nil {
		_ = stdout.Close()
		return err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		_ = stdout.Close()
		_ = stdin.Close()
		return err
	}

	if err := cmd.Start(); err != nil {
		_ = stdout.Close()
		_ = stdin.Close()
		_ = stderr.Close()
		return err
	}

	go func() {
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			log.Printf("mcp server stderr [%s]: %s", serverName, scanner.Text())
		}
		if err := scanner.Err(); err != nil {
			log.Printf("mcp server stderr [%s] read error: %v", serverName, err)
		}
	}()

	waitCh := make(chan error, 1)
	go func() {
		waitCh <- cmd.Wait()
	}()

	transport := newCommandTransport(stdout, stdin)
	if err := w.connect(ctx, transport); err != nil {
		_ = stdout.Close()
		_ = stdin.Close()
		_ = stderr.Close()
		_ = cmd.Process.Kill()
		<-waitCh
		return err
	}

	log.Printf("mcp command server %s started: %s %s", serverName, command, strings.Join(args, " "))

	w.appendCloser(func() error {
		_ = stdin.Close()
		_ = stdout.Close()
		_ = stderr.Close()
		var err error
		select {
		case err = <-waitCh:
		default:
			if cmd.Process != nil {
				_ = cmd.Process.Kill()
			}
			err = <-waitCh
		}
		if err != nil {
			log.Printf("mcp command server %s exited with error: %v", serverName, err)
		} else {
			log.Printf("mcp command server %s exited", serverName)
		}
		return err
	})

	return nil
}

func (w *ClientWrapper) appendCloser(fn func() error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.closers = append(w.closers, fn)
}

func (w *ClientWrapper) connect(ctx context.Context, transport sdk.Transport) error {
	sess, err := w.client.Connect(ctx, transport, nil)
	if err != nil {
		return err
	}
	w.session = sess
	kaCtx, cancel := context.WithCancel(context.Background())
	if prev := w.keepaliveCancel; prev != nil {
		prev()
	}
	w.keepaliveCancel = cancel
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-kaCtx.Done():
				return
			case <-ticker.C:
				_ = sess.Ping(context.Background(), nil)
			}
		}
	}()
	return nil
}

func (w *ClientWrapper) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	var errs []error
	if w.keepaliveCancel != nil {
		w.keepaliveCancel()
		w.keepaliveCancel = nil
	}
	if w.session != nil {
		if err := w.session.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	for i := len(w.closers) - 1; i >= 0; i-- {
		if err := w.closers[i](); err != nil {
			errs = append(errs, err)
		}
	}
	w.closers = nil
	return errors.Join(errs...)
}
