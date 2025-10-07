package mcp

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"sync"

	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

type commandTransport struct {
	conn *commandConnection
}

func newCommandTransport(r io.ReadCloser, w io.WriteCloser) *commandTransport {
	conn := newCommandConnection(r, w)
	return &commandTransport{conn: conn}
}

func (t *commandTransport) Connect(context.Context) (sdk.Connection, error) {
	return t.conn, nil
}

type commandConnection struct {
	reader    io.ReadCloser
	writer    io.WriteCloser
	incoming  chan readResult
	writeMu   sync.Mutex
	closeOnce sync.Once
	closeErr  error
}

type readResult struct {
	msg jsonrpc.Message
	err error
}

func newCommandConnection(r io.ReadCloser, w io.WriteCloser) *commandConnection {
	c := &commandConnection{
		reader:   r,
		writer:   w,
		incoming: make(chan readResult, 1),
	}
	go c.readLoop()
	return c
}

func (c *commandConnection) readLoop() {
	dec := json.NewDecoder(c.reader)
	for {
		var raw json.RawMessage
		if err := dec.Decode(&raw); err != nil {
			c.incoming <- readResult{err: err}
			close(c.incoming)
			return
		}
		msg, err := jsonrpc.DecodeMessage(raw)
		c.incoming <- readResult{msg: msg, err: err}
		if err != nil {
			close(c.incoming)
			return
		}
	}
}

func (c *commandConnection) Read(ctx context.Context) (jsonrpc.Message, error) {
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case res, ok := <-c.incoming:
		if !ok {
			return nil, io.EOF
		}
		if res.err != nil {
			return nil, res.err
		}
		return res.msg, nil
	}
}

func (c *commandConnection) Write(ctx context.Context, msg jsonrpc.Message) error {
	data, err := jsonrpc.EncodeMessage(msg)
	if err != nil {
		return err
	}
	data = append(data, '\n')
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	_, err = c.writer.Write(data)
	return err
}

func (c *commandConnection) Close() error {
	c.closeOnce.Do(func() {
		c.closeErr = errors.Join(c.reader.Close(), c.writer.Close())
	})
	return c.closeErr
}

func (c *commandConnection) SessionID() string { return "" }
