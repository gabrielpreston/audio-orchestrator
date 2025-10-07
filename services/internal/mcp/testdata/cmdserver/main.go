package main

import (
	"context"
	"log"

	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	server := sdk.NewServer(&sdk.Implementation{Name: "test-command", Version: "1.0.0"}, nil)

	type echoArgs struct {
		Message string `json:"message"`
	}

	sdk.AddTool(server, &sdk.Tool{Name: "echo", Description: "echo back messages"}, func(ctx context.Context, req *sdk.CallToolRequest, args echoArgs) (*sdk.CallToolResult, any, error) {
		return &sdk.CallToolResult{
			Content: []sdk.Content{
				&sdk.TextContent{Text: args.Message},
			},
		}, nil, nil
	})

	if err := server.Run(context.Background(), &sdk.StdioTransport{}); err != nil {
		log.Printf("server exited: %v", err)
	}
}
